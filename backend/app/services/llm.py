"""
LLM service supporting multiple providers: AWS Bedrock, NVIDIA, OpenAI, Anthropic.
Implements proper async with thread pool executor, retry logic, and circuit breaker.
"""

import json
import asyncio
import logging
from typing import AsyncIterator, Optional
from functools import partial
from concurrent.futures import ThreadPoolExecutor

import boto3
import httpx
from botocore.exceptions import ClientError, BotoCoreError

from app.core.config import settings
from app.core.circuit_breaker import get_bedrock_llm_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# Thread pool for running sync boto3 calls
_executor = ThreadPoolExecutor(max_workers=10)


class LLMServiceError(Exception):
    pass


class LLMRateLimitError(LLMServiceError):
    pass


class LLMService:
    
    def __init__(self, client=None, http_client=None):
        self._client = client  # boto3 client for Bedrock
        self._http_client = http_client  # httpx client for NVIDIA/OpenAI
        self._settings = settings
        self._provider = settings.LLM_PROVIDER.lower()
        self._setup_model_config()
        self.max_retries = 3
        self.base_delay = 1.0  # seconds
        self._metrics = {
            "generate_calls": 0,
            "stream_calls": 0,
        }
    
    def _setup_model_config(self):
        if self._provider == "nvidia":
            self.model_id = settings.NVIDIA_MODEL_ID
            self.base_url = settings.NVIDIA_BASE_URL
            self.api_key = settings.NVIDIA_API_KEY
        elif self._provider == "openai":
            self.model_id = "gpt-4o-mini"  # Default, can be overridden
            self.base_url = "https://api.openai.com/v1"
            self.api_key = settings.OPENAI_API_KEY if hasattr(settings, 'OPENAI_API_KEY') else ""
        elif self._provider == "anthropic":
            self.model_id = "claude-3-haiku-20240307"  # Default
            self.api_key = settings.ANTHROPIC_API_KEY if hasattr(settings, 'ANTHROPIC_API_KEY') else ""
        else:  # bedrock (default)
            self.model_id = settings.BEDROCK_MODEL_ID
            self.is_nova = "nova" in self.model_id.lower()
    
    @property
    def client(self):
        """Lazy initialization of boto3 client for Bedrock."""
        if self._provider != "bedrock":
            return None
        if self._client is None:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
        return self._client
    
    @property
    def http_client(self):
        """Lazy initialization of httpx client for HTTP-based providers."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._http_client
    
    def _mock_generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Mock response for cost-free benchmarking (no API calls)."""
        if "Strategy:" in prompt or "strategy" in prompt.lower():
            return "HYBRID"
        if "Write a brief" in prompt and "Question:" in prompt:
            q = prompt.split("Question:")[-1].split("\n")[0].strip()
            return f"IntelliDocs uses {q} for document intelligence. It uses RAG, pgvector, and hybrid search."
        if system_prompt and "CONTEXT FROM DOCUMENTS" in system_prompt:
            import re as _re
            blob = system_prompt.split("CONTEXT FROM DOCUMENTS:", 1)[-1]
            blocks = _re.findall(
                r"\[\d+\].*?\n(.*?)(?:\n---|\Z)", blob, flags=_re.S
            )
            evidence = (blocks[0] if blocks else "").strip()
            evidence = _re.sub(r"\s+", " ", evidence)
            if evidence:
                sentences = _re.split(r"(?<=[.!?])\s+", evidence)
                grounded = " ".join(s for s in sentences[:3] if s.strip()).strip()
                if grounded and not grounded.endswith((".", "?", "!")):
                    grounded += "."
                return f"{grounded} [1]" if grounded else "I could not find that in the documents."
        if system_prompt and "context" in system_prompt.lower():
            return "IntelliDocs is an AI document platform. PostgreSQL with pgvector, Redis caching, FastAPI, Next.js 14. AWS Bedrock for LLM and Titan embeddings. Hybrid search: semantic (pgvector) and keyword (BM25) with RRF. SSE streaming. Lambda and S3 for ingestion. Formats: PDF, DOCX, TXT, Markdown."
        return "IntelliDocs is an AI-powered document intelligence platform using RAG, pgvector, and hybrid search."

    def _build_request_body(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.4,
    ) -> dict:
        if self._provider == "bedrock":
            return self._build_bedrock_body(prompt, system_prompt, max_tokens, temperature)
        elif self._provider == "nvidia":
            return self._build_nvidia_body(prompt, system_prompt, max_tokens, temperature)
        elif self._provider == "openai":
            return self._build_openai_body(prompt, system_prompt, max_tokens, temperature)
        elif self._provider == "anthropic":
            return self._build_anthropic_body(prompt, system_prompt, max_tokens, temperature)
        else:
            return self._build_bedrock_body(prompt, system_prompt, max_tokens, temperature)
    
    def _build_bedrock_body(self, prompt: str, system_prompt: Optional[str], max_tokens: int, temperature: float) -> dict:
        if self.is_nova:
            body = {
                "schemaVersion": "messages-v1",
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                },
            }
            if system_prompt:
                body["system"] = [{"text": system_prompt}]
            return body
        else:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                body["system"] = system_prompt
            return body
    
    def _build_nvidia_body(self, prompt: str, system_prompt: Optional[str], max_tokens: int, temperature: float) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
    
    def _build_openai_body(self, prompt: str, system_prompt: Optional[str], max_tokens: int, temperature: float) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
    
    def _build_anthropic_body(self, prompt: str, system_prompt: Optional[str], max_tokens: int, temperature: float) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
    
    def _extract_response_text(self, response_body: dict) -> str:
        if self._provider == "bedrock":
            if self.is_nova:
                return response_body["output"]["message"]["content"][0]["text"]
            else:
                return response_body["content"][0]["text"]
        elif self._provider == "nvidia":
            return response_body["choices"][0]["message"]["content"]
        elif self._provider == "openai":
            return response_body["choices"][0]["message"]["content"]
        elif self._provider == "anthropic":
            return response_body["content"][0]["text"]
        else:
            return response_body["output"]["message"]["content"][0]["text"]
    
    def _sync_invoke_bedrock(self, body: dict) -> str:
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        response_body = json.loads(response["body"].read())
        return self._extract_response_text(response_body)
    
    async def _invoke_nvidia(self, body: dict) -> str:
        response = await self.http_client.post("/chat/completions", json=body)
        response.raise_for_status()
        return self._extract_response_text(response.json())
    
    async def _invoke_openai(self, body: dict) -> str:
        response = await self.http_client.post("/chat/completions", json=body)
        response.raise_for_status()
        return self._extract_response_text(response.json())
    
    async def _invoke_anthropic(self, body: dict) -> str:
        # Anthropic uses a different header format
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        response = await self.http_client.post(
            "/v1/messages",
            json=body,
            headers=headers,
        )
        response.raise_for_status()
        return self._extract_response_text(response.json())
    
    async def _invoke_provider(self, body: dict) -> str:
        if self._provider == "bedrock":
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                _executor,
                partial(self._sync_invoke_bedrock, body)
            )
        elif self._provider == "nvidia":
            return await self._invoke_nvidia(body)
        elif self._provider == "openai":
            return await self._invoke_openai(body)
        elif self._provider == "anthropic":
            return await self._invoke_anthropic(body)
        else:
            raise LLMServiceError(f"Unknown provider: {self._provider}")
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.4,
    ) -> str:
        self._metrics["generate_calls"] += 1
        
        if getattr(self._settings, "MOCK_LLM_AND_EMBEDDINGS", False):
            return self._mock_generate(prompt, system_prompt)
        
        # Validate API key for non-Bedrock providers
        if self._provider != "bedrock" and not self.api_key:
            logger.warning(f"No API key configured for {self._provider}, using mock response")
            return self._mock_generate(prompt, system_prompt)
        
        body = self._build_request_body(prompt, system_prompt, max_tokens, temperature)
        
        # Use circuit breaker only for Bedrock
        if self._provider == "bedrock":
            circuit = get_bedrock_llm_circuit()
            
            async def _do_generate():
                return await self._generate_with_retries(body)
            
            try:
                return await circuit.call(_do_generate)
            except CircuitOpenError as e:
                logger.warning(f"LLM circuit open, returning fallback response: {e}")
                return self._get_fallback_response(prompt)
            except Exception as e:
                logger.error(f"LLM generation failed after circuit breaker: {e}")
                return self._get_fallback_response(prompt)
        else:
            # For other providers, use direct invocation with retries
            try:
                return await self._generate_with_retries(body)
            except Exception as e:
                logger.error(f"LLM generation failed: {e}")
                return self._get_fallback_response(prompt)
    
    async def _generate_with_retries(self, body: dict) -> str:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                result = await self._invoke_provider(body)
                logger.info(f"LLM generation successful on attempt {attempt + 1}")
                return result
                
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:  # Rate limited
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(delay)
                elif e.response.status_code >= 500:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"Server error, retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"HTTP error: {e.response.status_code}")
                    raise LLMServiceError(f"Request failed: {e}") from e
                    
            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"Request error: {e}, retrying...")
                await asyncio.sleep(self.base_delay * (2 ** attempt))
                
            except ClientError as e:
                last_error = e
                error_code = e.response.get("Error", {}).get("Code", "") if hasattr(e, 'response') else ""
                
                if error_code in ["ThrottlingException", "ServiceUnavailableException"]:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"Rate limited, retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    logger.warning(f"Client error: {error_code}, retrying...")
                    await asyncio.sleep(self.base_delay)
                    
            except BotoCoreError as e:
                last_error = e
                logger.warning(f"BotoCore error: {e}, retrying...")
                await asyncio.sleep(self.base_delay * (2 ** attempt))
                
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error in LLM generation: {e}")
                raise LLMServiceError(f"LLM generation failed: {e}") from e
        
        # All retries exhausted
        logger.error(f"All {self.max_retries} retries exhausted")
        raise LLMRateLimitError(f"LLM service unavailable after {self.max_retries} retries") from last_error
    
    def _get_fallback_response(self, prompt: str) -> str:
        return (
            "I apologize, but the AI service is temporarily unavailable. "
            "This is likely due to high demand or a temporary service disruption. "
            "Please try again in a moment. If you were asking about your documents, "
            "I recommend checking that your documents have finished processing."
        )
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.4,
    ) -> AsyncIterator[str]:
        self._metrics["stream_calls"] += 1
        
        if getattr(self._settings, "MOCK_LLM_AND_EMBEDDINGS", False):
            text = self._mock_generate(prompt, system_prompt)
            for c in text:
                yield c
            return
        
        # Validate API key
        if self._provider != "bedrock" and not self.api_key:
            logger.warning(f"No API key for {self._provider}, using mock response")
            text = self._mock_generate(prompt, system_prompt)
            for c in text:
                yield c
            return
        
        # Check circuit for Bedrock
        if self._provider == "bedrock":
            circuit = get_bedrock_llm_circuit()
            if circuit.state.value == "open":
                logger.warning("LLM circuit open, yielding fallback response")
                yield self._get_fallback_response(prompt)
                return
        
        body = self._build_request_body(prompt, system_prompt, max_tokens, temperature)
        
        try:
            if self._provider == "bedrock":
                async for token in self._stream_bedrock(body):
                    yield token
            elif self._provider == "nvidia":
                async for token in self._stream_nvidia(body):
                    yield token
            elif self._provider == "openai":
                async for token in self._stream_openai(body):
                    yield token
            else:
                # Fallback for unsupported streaming
                text = await self.generate(prompt, system_prompt, max_tokens, temperature)
                for c in text:
                    yield c
                    
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield self._get_fallback_response(prompt)
    
    async def _stream_bedrock(self, body: dict) -> AsyncIterator[str]:
        loop = asyncio.get_event_loop()
        
        def sync_stream():
            response = self.client.invoke_model_with_response_stream(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            for event in response["body"]:
                chunk = json.loads(event["chunk"]["bytes"])
                if self.is_nova:
                    if "contentBlockDelta" in chunk:
                        delta = chunk["contentBlockDelta"].get("delta", {})
                        if "text" in delta:
                            yield delta["text"]
                else:
                    if chunk.get("type") == "content_block_delta":
                        delta = chunk.get("delta", {})
                        if "text" in delta:
                            yield delta["text"]
        
        # Run in executor
        import queue
        result_queue: queue.Queue = queue.Queue()
        
        def run():
            try:
                for token in sync_stream():
                    result_queue.put(("token", token))
                result_queue.put(("done", None))
            except Exception as e:
                result_queue.put(("error", str(e)))
        
        import threading
        thread = threading.Thread(target=run)
        thread.start()
        
        while True:
            try:
                msg_type, msg_data = await loop.run_in_executor(
                    None,
                    lambda: result_queue.get(timeout=30)
                )
                if msg_type == "token":
                    yield msg_data
                elif msg_type == "done":
                    break
                elif msg_type == "error":
                    logger.error(f"Streaming error: {msg_data}")
                    break
            except queue.Empty:
                break
        
        thread.join(timeout=5)
    
    async def _stream_nvidia(self, body: dict) -> AsyncIterator[str]:
        body["stream"] = True
        
        async with self.http_client.stream("POST", "/chat/completions", json=body) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if chunk.get("choices"):
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                    except json.JSONDecodeError:
                        continue
    
    async def _stream_openai(self, body: dict) -> AsyncIterator[str]:
        async with self.http_client.stream("POST", "/chat/completions", json=body) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if chunk.get("choices"):
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                    except json.JSONDecodeError:
                        continue
    
    async def route_query(self, query: str) -> str:
        routing_prompt = f"""Analyze this query and determine the best search strategy.

Query: {query}

Respond with ONLY one word - one of these strategies:
- SEMANTIC: For conceptual questions, summaries, explanations
- KEYWORD: For specific terms, names, dates, exact phrases  
- HYBRID: For questions needing both concepts and specific facts

Strategy:"""
        
        try:
            response = await self.generate(
                routing_prompt,
                max_tokens=20,
                temperature=0,
            )
            
            strategy = response.strip().upper().split()[0] if response.strip() else "HYBRID"
            if strategy not in ["SEMANTIC", "KEYWORD", "HYBRID"]:
                logger.info(f"Unknown strategy '{strategy}', defaulting to HYBRID")
                return "HYBRID"
            
            logger.info(f"Query routed to {strategy} strategy")
            return strategy
            
        except LLMServiceError:
            logger.warning("Query routing failed, defaulting to HYBRID")
            return "HYBRID"

    def reset_metrics(self) -> None:
        self._metrics = {
            "generate_calls": 0,
            "stream_calls": 0,
        }

    def get_metrics(self) -> dict:
        return dict(self._metrics)

    async def close(self):
        if self._http_client:
            await self._http_client.aclose()


def create_llm_service(client=None, http_client=None, model_id: str | None = None, provider: str | None = None) -> LLMService:
    svc = LLMService(client=client, http_client=http_client)
    if provider:
        svc._provider = provider.lower()
        svc._setup_model_config()
    if model_id:
        svc.model_id = model_id
    return svc


# Default singleton
llm_service = create_llm_service()

# Auxiliary singleton for cheap tasks
aux_llm_service = create_llm_service(
    model_id=settings.BEDROCK_AUX_MODEL_ID if settings.LLM_PROVIDER == "bedrock" else None
)