# Responses API Migration Plan - SurfCastAI

## Executive Summary

This document provides a detailed plan for migrating surfCastAI from the Chat Completions API to the Responses API for GPT-5 models. The Responses API is OpenAI's recommended interface for GPT-5, offering optimized performance and cleaner syntax.

**Status:** OPTIONAL ENHANCEMENT (Priority 3)
**Effort:** Medium (2-3 hours development + testing)
**Risk:** Low (can maintain backward compatibility)
**Benefit:** 10-20% performance improvement + cleaner code

---

## Background: Chat Completions API vs Responses API

### Current: Chat Completions API

```python
response = await client.chat.completions.create(
    model="gpt-5-mini",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": url, "detail": "high"}}
        ]}
    ],
    max_completion_tokens=4000,
    temperature=1.0
)
text = response.choices[0].message.content
```

### Future: Responses API

```python
response = await client.responses.create(
    model="gpt-5-mini",
    instructions=system_prompt,
    input=[
        {"role": "user", "content": user_prompt},
        {"role": "user", "content": [
            {"type": "input_image", "image_url": url}
        ]}
    ],
    reasoning={"effort": "medium"},
    text={"verbosity": "medium"},
    max_output_tokens=4000,
    temperature=1.0
)
text = response.output_text
```

### Key Differences

| Aspect | Chat Completions API | Responses API |
|--------|---------------------|---------------|
| **Prompts** | `messages` with roles | `instructions` + `input` |
| **Images** | `image_url` type | `input_image` type |
| **Output** | `response.choices[0].message.content` | `response.output_text` |
| **Tokens** | `max_completion_tokens` | `max_output_tokens` |
| **Reasoning** | Not supported | `reasoning={"effort": "..."}` |
| **Verbosity** | Not supported | `text={"verbosity": "..."}` |
| **Performance** | Standard | Optimized for GPT-5 |

---

## Migration Strategy

### Phase 1: Create Responses API Method (New Code)

**Goal:** Add new `_call_responses_api()` method alongside existing `_call_openai_api()`

**Files to Modify:**
- `src/forecast_engine/forecast_engine.py`

**Implementation:**

```python
async def _call_responses_api(
    self,
    instructions: str,
    user_prompt: str,
    image_urls: Optional[List[str]] = None,
    detail: str = "auto",
    reasoning_effort: Optional[str] = None,
    verbosity: Optional[str] = None
) -> str:
    """
    Call the OpenAI Responses API to generate text with optional image inputs.

    This is the recommended API for GPT-5 models, offering better performance
    and native support for reasoning_effort and verbosity parameters.

    Args:
        instructions: System instructions for the model (replaces system_prompt)
        user_prompt: User prompt containing specific request
        image_urls: Optional list of image URLs/paths (max 10)
        detail: Image resolution - "auto", "low", or "high"
        reasoning_effort: "minimal", "low", "medium", or "high"
        verbosity: "low", "medium", or "high"

    Returns:
        Generated text
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        self.logger.error("OpenAI package not installed. Please install it with: pip install openai")
        return "Error: OpenAI package not installed."

    try:
        # Initialize client
        client = AsyncOpenAI(api_key=self.openai_api_key)

        # Build input content
        input_content = []

        # Add text prompt
        input_content.append({
            "role": "user",
            "content": user_prompt
        })

        # Add images if provided
        if image_urls:
            image_items = []
            for url in image_urls[:10]:  # GPT-5 limit: 10 images
                # Convert local paths to base64 data URLs
                if url.startswith('data/'):
                    import base64
                    from pathlib import Path
                    try:
                        image_data = base64.b64encode(Path(url).read_bytes()).decode()
                        ext = Path(url).suffix.lower()
                        mime_type = {
                            '.png': 'image/png',
                            '.jpg': 'image/jpeg',
                            '.jpeg': 'image/jpeg',
                            '.gif': 'image/gif'
                        }.get(ext, 'image/png')
                        url = f"data:{mime_type};base64,{image_data}"
                    except Exception as e:
                        self.logger.warning(f"Failed to load image {url}: {e}")
                        continue

                image_items.append({
                    "type": "input_image",
                    "image_url": url
                    # Note: 'detail' is not supported in Responses API input_image
                    # Resolution is auto-determined based on model
                })

            if image_items:
                input_content.append({
                    "role": "user",
                    "content": image_items
                })

        # Build request kwargs
        request_kwargs = {
            "model": self.openai_model,
            "instructions": instructions,
            "input": input_content,
        }

        # Add optional parameters
        if self.max_tokens is not None:
            request_kwargs["max_output_tokens"] = self.max_tokens

        if self.temperature is not None:
            request_kwargs["temperature"] = self.temperature

        # Add GPT-5 specific parameters
        if reasoning_effort:
            request_kwargs["reasoning"] = {"effort": reasoning_effort}

        if verbosity:
            request_kwargs["text"] = {"verbosity": verbosity}

        # Call Responses API
        response = await client.responses.create(**request_kwargs)

        # Extract and return content
        if hasattr(response, 'output_text') and response.output_text:
            return response.output_text.strip()
        else:
            self.logger.error("No output_text returned from Responses API")
            return ""

    except Exception as e:
        self.logger.error(f"Error calling Responses API: {e}")
        return f"Error generating forecast: {str(e)}"
```

**Estimated Effort:** 1 hour

---

### Phase 2: Add Configuration Toggle

**Goal:** Allow switching between Chat Completions and Responses API via config

**Files to Modify:**
- `config/config.yaml`
- `src/forecast_engine/forecast_engine.py` (__init__)

**Config Changes:**

```yaml
openai:
  model: gpt-5-mini
  api_key: ${OPENAI_API_KEY}  # Use env var instead of hardcoded
  max_tokens: 4000
  use_responses_api: true  # NEW: Toggle between APIs

  # Responses API specific settings (only used if use_responses_api: true)
  responses_api:
    reasoning_effort: medium  # minimal, low, medium, high
    verbosity: medium  # low, medium, high
```

**Code Changes:**

```python
# In ForecastEngine.__init__()
self.use_responses_api = self.config.get('openai', 'use_responses_api', False)
self.reasoning_effort = self.config.get('openai', 'responses_api', {}).get('reasoning_effort')
self.verbosity = self.config.get('openai', 'responses_api', {}).get('verbosity')
```

**Estimated Effort:** 30 minutes

---

### Phase 3: Update Method Routing

**Goal:** Route API calls to correct method based on config

**Files to Modify:**
- `src/forecast_engine/forecast_engine.py` (_generate_main_forecast, _generate_shore_forecast, etc.)

**Implementation:**

Add a router method:

```python
async def _call_api(
    self,
    system_prompt: str,
    user_prompt: str,
    image_urls: Optional[List[str]] = None,
    detail: str = "auto"
) -> str:
    """
    Route API call to Chat Completions or Responses API based on config.

    Args:
        system_prompt: System prompt (maps to 'instructions' in Responses API)
        user_prompt: User prompt
        image_urls: Optional image URLs
        detail: Image detail level (Chat Completions only)

    Returns:
        Generated text
    """
    if self.use_responses_api:
        # Use Responses API (recommended for GPT-5)
        return await self._call_responses_api(
            instructions=system_prompt,
            user_prompt=user_prompt,
            image_urls=image_urls,
            detail=detail,
            reasoning_effort=self.reasoning_effort,
            verbosity=self.verbosity
        )
    else:
        # Use Chat Completions API (legacy/fallback)
        return await self._call_openai_api(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_urls=image_urls,
            detail=detail
        )
```

Then update all API call sites:

```python
# BEFORE:
analysis = await self._call_openai_api(
    system_prompt=self.templates.get_template('caldwell').get('system_prompt', ''),
    user_prompt=PRESSURE_CHART_ANALYSIS_PROMPT,
    image_urls=pressure_charts,
    detail=pressure_detail
)

# AFTER:
analysis = await self._call_api(
    system_prompt=self.templates.get_template('caldwell').get('system_prompt', ''),
    user_prompt=PRESSURE_CHART_ANALYSIS_PROMPT,
    image_urls=pressure_charts,
    detail=pressure_detail
)
```

**Call Sites to Update:**
1. Pressure chart analysis (~line 546)
2. Satellite analysis (~line 571)
3. SST analysis (~line 608)
4. Main forecast generation (~line 664)
5. Shore forecast generation (~line 715)
6. Daily forecast generation (~line 768)

**Estimated Effort:** 30 minutes

---

### Phase 4: Testing & Validation

**Goal:** Verify both APIs work correctly with same results

**Test Plan:**

1. **Test Chat Completions API (Current)**
   ```bash
   # Ensure use_responses_api: false in config
   python src/main.py run --mode forecast --bundle <recent_bundle_id>
   ```
   - Verify forecast generates successfully
   - Check all debug files populated
   - Validate output quality

2. **Test Responses API (New)**
   ```bash
   # Set use_responses_api: true in config
   python src/main.py run --mode forecast --bundle <same_bundle_id>
   ```
   - Verify forecast generates successfully
   - Check all debug files populated
   - Compare output with Chat Completions version

3. **A/B Comparison**
   - Compare token usage (should be similar)
   - Compare generation time (Responses API should be ~10-20% faster)
   - Compare forecast quality (should be equivalent or better)
   - Compare costs (should be identical)

4. **Edge Cases**
   - Test with 0 images (text only)
   - Test with 1 image
   - Test with 10 images (max limit)
   - Test with different reasoning_effort values
   - Test with different verbosity values

5. **Error Handling**
   - Test with invalid API key
   - Test with network timeout
   - Test with malformed image URLs
   - Test with missing image files

**Estimated Effort:** 1 hour

---

### Phase 5: Documentation & Deployment

**Goal:** Document changes and prepare for production rollout

**Tasks:**

1. **Update README.md**
   - Document use_responses_api configuration option
   - Explain reasoning_effort and verbosity parameters
   - Provide migration guide for users

2. **Update CLAUDE.md**
   - Note Responses API implementation status
   - Document configuration options

3. **Create Migration Guide**
   - Document differences between APIs
   - Provide rollback instructions
   - List benefits and trade-offs

4. **Production Rollout**
   - Deploy with use_responses_api: false (default)
   - Monitor for 1 week
   - Enable use_responses_api: true
   - Monitor performance improvements

**Estimated Effort:** 30 minutes

---

## Detailed Code Changes

### File: src/forecast_engine/forecast_engine.py

**Location 1: Add import at top (after line 8)**
```python
import asyncio
import logging
import os
import json
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from pathlib import Path
```
No changes needed - already correct

**Location 2: __init__ method (after line 94)**
```python
# Add after self.quality_threshold = ...
self.use_responses_api = self.config.get('openai', 'use_responses_api', False)
self.reasoning_effort = self.config.get('openai', 'responses_api', {}).get('reasoning_effort')
self.verbosity = self.config.get('openai', 'responses_api', {}).get('verbosity')

# Log API choice
if self.use_responses_api:
    self.logger.info(f"Using Responses API with reasoning_effort={self.reasoning_effort}, verbosity={self.verbosity}")
else:
    self.logger.info("Using Chat Completions API")
```

**Location 3: Add new method (after line 868, before _call_openai_api)**
```python
async def _call_responses_api(
    self,
    instructions: str,
    user_prompt: str,
    image_urls: Optional[List[str]] = None,
    detail: str = "auto",
    reasoning_effort: Optional[str] = None,
    verbosity: Optional[str] = None
) -> str:
    """
    [Full implementation from Phase 1 above]
    """
    # ... (full code from Phase 1)
```

**Location 4: Add router method (after _call_responses_api)**
```python
async def _call_api(
    self,
    system_prompt: str,
    user_prompt: str,
    image_urls: Optional[List[str]] = None,
    detail: str = "auto"
) -> str:
    """
    [Full implementation from Phase 3 above]
    """
    # ... (full code from Phase 3)
```

**Location 5: Keep _call_openai_api unchanged**
- No changes to existing method
- Maintains backward compatibility

**Location 6-11: Update API call sites**
Replace all instances of:
```python
await self._call_openai_api(...)
```
With:
```python
await self._call_api(...)
```

Specific lines to change:
- Line ~546: Pressure chart analysis
- Line ~571: Satellite analysis
- Line ~608: SST analysis
- Line ~664: Main forecast
- Line ~715: Shore forecast
- Line ~768: Daily forecast

---

### File: config/config.yaml

**Add after line 9 (after max_tokens):**
```yaml
openai:
  model: gpt-5-mini
  api_key: ${OPENAI_API_KEY}  # CHANGED: Use env var for security
  max_tokens: 4000
  use_responses_api: false  # NEW: Set to true to use Responses API (recommended for GPT-5)

  # NEW: Responses API specific settings (only used if use_responses_api: true)
  responses_api:
    reasoning_effort: medium  # Options: minimal, low, medium, high
    verbosity: medium  # Options: low, medium, high
```

---

## Testing Checklist

### Pre-Migration Testing (Chat Completions API)
- [ ] Run full forecast generation with current code
- [ ] Verify all 4 forecast sections generate
- [ ] Check image analysis files (pressure, satellite, SST) populated
- [ ] Validate output formats (MD, HTML, PDF, JSON)
- [ ] Note generation time and token usage

### Post-Migration Testing (Responses API)
- [ ] Enable use_responses_api: true in config
- [ ] Run forecast generation with same bundle
- [ ] Verify all 4 forecast sections generate
- [ ] Check image analysis files populated
- [ ] Validate output formats
- [ ] Compare generation time (should be faster)
- [ ] Compare token usage (should be similar)
- [ ] Compare forecast quality (should be equal/better)

### Edge Case Testing
- [ ] Test with 0 images (text only)
- [ ] Test with 1 image
- [ ] Test with 10 images (max)
- [ ] Test reasoning_effort: minimal
- [ ] Test reasoning_effort: low
- [ ] Test reasoning_effort: medium
- [ ] Test reasoning_effort: high
- [ ] Test verbosity: low
- [ ] Test verbosity: medium
- [ ] Test verbosity: high

### Error Handling Testing
- [ ] Test with invalid API key (should fail gracefully)
- [ ] Test with network timeout (should timeout correctly)
- [ ] Test with malformed image URL (should skip and continue)
- [ ] Test with missing image file (should skip and continue)
- [ ] Test API fallback (if Responses API fails, falls back to Chat Completions)

### Backward Compatibility Testing
- [ ] Test with use_responses_api: false (should work as before)
- [ ] Test with older OpenAI library version (should detect and fallback)
- [ ] Test with non-GPT-5 models (should work with Chat Completions)

---

## Rollback Plan

If issues arise with Responses API migration:

1. **Immediate Rollback:**
   ```yaml
   # In config.yaml
   openai:
     use_responses_api: false
   ```
   No code changes needed - system falls back to Chat Completions API

2. **Code Rollback (if needed):**
   - Revert commits related to Responses API
   - Or simply keep use_responses_api: false

3. **Partial Rollback:**
   - Use Responses API for text-only calls
   - Use Chat Completions for multimodal calls
   - Requires custom routing logic

---

## Benefits Summary

### Performance Improvements
- 10-20% faster response times (per OpenAI documentation)
- Better handling of multimodal inputs
- More efficient token usage with reasoning_effort control

### Code Quality
- Cleaner API surface (instructions vs messages)
- Native support for GPT-5 features (reasoning_effort, verbosity)
- More explicit parameter names (max_output_tokens vs max_completion_tokens)

### Cost Optimization
- reasoning_effort: "minimal" for simple tasks reduces tokens
- verbosity control prevents unnecessarily verbose outputs
- Same pricing, better efficiency

### Future-Proofing
- Responses API is OpenAI's recommended interface for GPT-5
- Better support for future GPT models
- Cleaner migration path to GPT-6 when released

---

## Risks & Mitigation

### Risk 1: Breaking Changes in Responses API
**Likelihood:** Low
**Impact:** Medium
**Mitigation:** Maintain backward compatibility with Chat Completions API via toggle

### Risk 2: Library Version Incompatibility
**Likelihood:** Medium
**Impact:** Low
**Mitigation:** Check for responses attribute on client, fallback if not available

### Risk 3: Different Output Quality
**Likelihood:** Low
**Impact:** High
**Mitigation:** A/B test thoroughly before production rollout

### Risk 4: Increased Complexity
**Likelihood:** Medium
**Impact:** Low
**Mitigation:** Good documentation, clean separation of concerns

---

## Timeline

**Total Estimated Effort:** 3.5 hours

| Phase | Task | Duration |
|-------|------|----------|
| 1 | Create _call_responses_api method | 1 hour |
| 2 | Add configuration toggle | 30 min |
| 3 | Update method routing | 30 min |
| 4 | Testing & validation | 1 hour |
| 5 | Documentation & deployment | 30 min |

**Recommended Schedule:**
- Week 1: Implement Phases 1-3 (2 hours)
- Week 2: Testing & validation (1 hour)
- Week 3: Documentation & staged rollout (30 min)
- Week 4: Monitor production performance

---

## Success Criteria

Migration is successful if:
- [ ] All forecasts generate successfully with Responses API
- [ ] Generation time improves by 10-20%
- [ ] Forecast quality is equal or better
- [ ] Token usage is similar or reduced
- [ ] No increase in error rates
- [ ] Backward compatibility maintained
- [ ] All tests pass

---

## Recommendation

**Priority:** 3 (Future Enhancement)
**Urgency:** Low
**Complexity:** Medium

**Recommended Action:**
1. Implement after production deployment is stable
2. Run A/B tests for 1-2 weeks
3. Monitor performance improvements
4. Roll out gradually (canary deployment)

**Not Recommended If:**
- Production deployment not yet stable
- Team lacks bandwidth for testing
- Current Chat Completions API meeting all needs

---

## References

- OpenAI GPT-5 Cookbook: https://cookbook.openai.com/examples/gpt-5/gpt-5_new_params_and_tools
- OpenAI Responses API Documentation: https://platform.openai.com/docs/api-reference/responses
- OpenAI Python Library: https://github.com/openai/openai-python

---

*Migration plan created: October 4, 2025*
*Review by: Context7 + Claude Code*
