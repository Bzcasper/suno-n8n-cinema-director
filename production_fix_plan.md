### Plan for Fixing Memory Cleanup in `modal_video_gen.py` (v3.5 Enhanced)

**Objective:** Address the root cause of video generation failing after the first scene due to VRAM/GPU memory exhaustion. The issue stems from incomplete PyTorch CUDA cache clearing between iterations in the clip generation loop, preventing subsequent scenes from allocating necessary GPU resources. This plan incorporates the provided diagnosis and fix to ensure all scenes render successfully.

**Root Cause Summary (from Provided Analysis):**
- The pipeline works for the first scene (models load correctly), but subsequent scenes fail due to OOM errors.
- `del image, frames` and `gc.collect()` are present but insufficient; `torch.cuda.empty_cache()` is missing, which is critical for releasing VRAM in PyTorch-based diffusion models (Flux and CogVideoX).
- Without proper cleanup, GPU memory accumulates, causing failures on the second+ iterations.

**Step-by-Step Implementation Plan:**

1. **Locate the Cleanup Block in the Scene Loop:**
   - Target: The `create_music_video` method, within the `for i, scene in enumerate(storyboard):` loop.
   - Current location: After `clips.append(clip)`, around line ~360 in the existing code.
   - Existing code: `del image, frames; import gc; gc.collect(); print(f"[SCENE {i + 1}] Completed")`

2. **Add Mandatory PyTorch CUDA Cache Clearing:**
   - Insert `torch.cuda.empty_cache()` immediately after `gc.collect()`.
   - Ensure `import torch` is available (already imported globally or add locally if needed).
   - This forces immediate release of GPU memory, preventing accumulation across scenes.

3. **Enhanced Error Handling (Already Present):**
   - The `try-except` block with `continue` is correct; it skips failed scenes instead of crashing the entire pipeline.
   - No changes needed here, but confirm it's in place to allow partial success.

4. **Full Corrected Cleanup Block:**
   - Replace the existing cleanup with:
     ```
     # Cleanup - CRITICAL FIX
     del image, frames
     import gc
     import torch  # Ensure imported
     
     gc.collect()
     torch.cuda.empty_cache()  # <-- Forces VRAM release
     
     print(f"[SCENE {i + 1}] Completed")
     ```

5. **Validation Steps (Post-Implementation):**
   - Deploy the updated code: `modal deploy modal_video_gen.py`.
   - Test with a multi-scene storyboard (e.g., 10-14 scenes) to confirm all scenes render.
   - Monitor GPU memory usage in Modal logs; expect stable VRAM across iterations.
   - If issues persist, check for model offloading (`enable_model_cpu_offload()`) being properly applied.

**Expected Outcomes:**
- All scenes will generate and animate without OOM failures.
- Video length will match the full song duration instead of stopping after 1-2 scenes.
- Improved stability for concurrent requests (e.g., from Tampermonkey).

**Risks & Mitigations:**
- Slight performance overhead from cache clearing; acceptable for reliability.
- If `torch.cuda.empty_cache()` causes delays, consider adding a small sleep (e.g., `time.sleep(0.1)`), but test first.
- Ensure A100-80GB GPU is sufficient; if not, consider upgrading to H100.

**Next Steps:**
- Apply the fix in a controlled edit session.
- After deployment, run a full test with "Mob Ties and Money" or similar to verify multi-scene completion.
- If needed, review `n8n_enhanced_workflow.json` for upstream adjustments (e.g., retry logic).

This plan resolves the memory exhaustion issue, enabling complete video generation.

---

# 🏗️ Suno Pipeline Upgrade Plan v3.1: Gemini Integration

**Status:** Draft
**Target Version:** v3.1 (The "Bicameral" Mind)
**Objective:** Integrate Google Gemini 1.5 Pro/Flash to replace/augment OpenAI for multimodal analysis and metadata generation.

---

## 🧠 Architectural Logic (Why Gemini?)

Currently, our system ("The Mind") relies heavily on OpenAI. Integrating Gemini offers distinct advantages for the Suno pipeline:

1.  **Native Audio Understanding:** Gemini 1.5 Pro can "listen" to the raw Suno MP3/WAV files directly (multimodal input) rather than relying solely on text descriptions.
2.  **Cost Efficiency:** Gemini 1.5 Flash is significantly cheaper for high-volume metadata generation tasks.
3.  **Video Context:** Can analyze the generated video frames in the "Factory" layer to ensure the visuals match the beat/vibe.

---

## 📋 Implementation Checklist

### Phase 1: Infrastructure & Auth (The Backbone)
- [ ] **Obtain Credentials:**
    - Get API Key from [Google AI Studio](https://aistudio.google.com/) (Free tier available) OR
    - Enable Vertex AI API in Google Cloud Console (if using GCP Service Account from Phase 2 of original setup).
- [ ] **Environment Variables:**
    - Add `GOOGLE_GENERATIVE_AI_API_KEY` to:
        - n8n Credentials
        - Modal Secrets (`suno-video-secrets`)
        - Vercel/Node.js Environment

### Phase 2: The Mind (Intelligence Layer Updates)
*Target File: `intelligence_api.py` or Vercel AI SDK logic*

- [ ] **Install Google Provider:**
    ```bash
    npm install @ai-sdk/google
    # or for Python
    pip install google-generativeai
    ```
- [ ] **Update `analyzeVibe()` function:**
    - **Current:** Uses GPT-4o Vision on Cover Art.
    - **Upgrade:** Use Gemini 1.5 Pro to analyze **Cover Art + Audio Snippet**.
    - **Benefit:** More accurate "Vibe" tags (e.g., detecting tempo/instruments).

### Phase 3: The Factory (Render Farm Updates)
*Target File: `modal_video_gen.py`*

- [ ] **Inject Gemini into Prompt Generation:**
    - Replace the Llama 3.1 logic (or augment it) with Gemini 1.5 Flash for faster prompt variations.
    - *Note:* Gemini Flash has lower latency, reducing "Cold Start" impact.

### Phase 4: The Brain (n8n Workflow Updates)
*Target File: `n8n_enhanced_workflow.json`*

- [ ] **Replace "Intelligence API Call" Node:**
    - If using LangChain nodes: Switch Model to `ChatGoogleGenerativeAI`.
    - If using HTTP Request: Update endpoint to `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent`.
- [ ] **New Node: "Audio Analyzer"**:
    - Pass the downloaded MP3 URL directly to Gemini.
    - Ask: *"Analyze this song's structure. Identify the BPM, Genre, and Mood for video generation."*

---

## 🛠️ Code Artifacts

### A. Vercel AI SDK Implementation (The Mind)
Use this pattern to ensure Type-Safe responses (Zod) with Gemini.

```typescript
import { google } from '@ai-sdk/google';
import { generateObject } from 'ai';
import { z } from 'zod';

// Define the Schema for Suno Metadata
const SunoMetadataSchema = z.object({
  title: z.string().describe("Viral YouTube title"),
  description: z.string().describe("SEO optimized description"),
  tags: z.array(z.string()).max(15),
  visual_style_prompt: z.string().describe("Prompt for the video generator")
});

export async function generateGeminiMetadata(imageUrl: string, audioContext: string) {
  const result = await generateObject({
    model: google('models/gemini-1.5-pro-latest'),
    schema: SunoMetadataSchema,
    messages: [
      {
        role: 'user',
        content: [
          { type: 'text', text: `Analyze this cover art and song context: ${audioContext}` },
          { type: 'image', image: imageUrl }
        ],
      },
    ],
  });

  return result.object;
}
```

### B. Modal Python Implementation (The Factory)

Update `modal_video_gen.py` to use Gemini for creative direction if Llama 3.1 is too heavy.

```python
import google.generativeai as genai
import os

# Initialize inside the container
def get_gemini_director(prompt_context):
    genai.configure(api_key=os.environ["GOOGLE_GENERATIVE_AI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    response = model.generate_content(
        f"You are a music video director. {prompt_context} \n"
        "Output ONLY a Python list of 5 visual scene descriptions."
    )
    return response.text
```

-----

## ⚠️ Migration Risks & Circuit Breakers

| Risk | Mitigation Strategy |
|------|---------------------|
| **Safety Filters** | Gemini has stricter safety filters than OpenAI. We must implement `HarmCategory.BLOCK_NONE` carefully in the API config to avoid blocking innocuous song lyrics. |
| **Rate Limits** | Free tier (AI Studio) has limits. Implement **Exponential Backoff** in n8n if hitting 429 errors. |
| **Token Usage** | Audio analysis consumes more tokens. Use `Gemini 1.5 Flash` for audio, `Pro` for complex reasoning. |

-----

## 🚀 Execution Order

1.  **Stop the Factory:** Pause the n8n webhook.
2.  **Deploy Secrets:** `modal secret create suno-video-secrets GOOGLE_API_KEY=...`
3.  **Update The Mind:** Deploy new Node.js/Python intelligence code.
4.  **Update n8n:** Swap the LLM nodes.
5.  **Test:** Run a single song with `DEBUG=true` to verify Zod schema validation.
6.  **Restart:** Enable the webhook.