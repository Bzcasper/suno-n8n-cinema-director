"""
Suno Video Factory v3.1 - "The Cinema Director"
Architecture: A100-80GB Single-Container | Flux.1 [dev] | CogVideoX-5B | Llama 3.1
Integration: FastAPI Webhook for n8n
"""

import modal
import os
import json
from pathlib import Path

# ==============================================================================
# 📦 CONFIGURATION & VOLUMES
# ==============================================================================
app = modal.App("suno-video-factory-v3-1")

# Shared volumes for model caching (saves ~100GB download time on cold boot)
model_volume = modal.Volume.from_name("suno-model-cache", create_if_missing=True)
asset_volume = modal.Volume.from_name("suno-asset-cache", create_if_missing=True)

# ==============================================================================
# 🧠 THE BRAIN: Llama 3.1 Prompt Engineering
# ==============================================================================
DIRECTOR_SYSTEM_PROMPT = """
You are a visionary Music Video Director. Your goal is to create a visually coherent, cinematic storyline for a song.

CRITICAL RULES:
1. **Consistency**: You MUST define a "Visual Style" and "Protagonist" at the start and reuse them for EVERY scene.
2. **Cinematography**: Use professional camera terms (e.g., "low angle", "85mm lens", "volumetric lighting", "bokeh").
3. **Motion**: For each scene, specify a MOTION prompt optimized for AI video generators. Use keywords: "slow pan", "zoom in", "static camera", "tracking shot".
4. **Format**: Output ONLY a valid JSON array.

Example Output Structure:
[
  {
    "start": 0.0,
    "end": 4.0,
    "visual_prompt": "Cyberpunk style. A young woman with neon blue hair standing in rain, looking at a hologram. 85mm lens, depth of field, neon lights reflecting on wet pavement. High detail, 8k.",
    "motion_prompt": "The camera slowly zooms in on the woman's face. Smooth motion."
  }
]
"""

# ==============================================================================
# 🏭 THE FACTORY ENVIRONMENT
# ==============================================================================
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "git")
    .pip_install(
        "fastapi[standard]",  # <--- CRITICAL: Required for n8n webhook
        "torch==2.4.0",
        "diffusers==0.30.0",
        "transformers==4.44.0",
        "accelerate==0.33.0",
        "sentencepiece",
        "moviepy==1.0.3",
        "bitsandbytes",
        "whisperx==3.1.1",
        "opencv-python-headless",
        "numpy<2.0.0",
    )
)


@app.cls(
    image=image,
    gpu="A100-80GB",  # CRITICAL: 40GB cards will OOM with Flux+CogVideo+Llama
    timeout=3600,  # 1 Hour Max for long songs
    volumes={"/root/models": model_volume, "/tmp/assets": asset_volume},
    secrets=[modal.Secret.from_name("suno-video-secrets")],
)
class VideoFactory:
    def enter(self):
        """Zero-Latency Bootstrap: Load all 3 models into VRAM"""
        import torch
        from diffusers.pipelines.flux.pipeline_flux import FluxPipeline
        from diffusers.pipelines.cogvideo.pipeline_cogvideox_image2video import (
            CogVideoXImageToVideoPipeline,
        )
        from transformers import AutoTokenizer, AutoModelForCausalLM

        self.device = "cuda"
        torch.backends.cuda.matmul.allow_tf32 = True

        # 1. Load Director (Llama 3.1 8B) - 4-bit Quantized
        print("[BOOT] Loading Director (Llama 3.1)...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
            token=os.environ["HF_TOKEN"],
            cache_dir="/root/models",
        )
        self.director = AutoModelForCausalLM.from_pretrained(
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
            device_map="auto",
            load_in_4bit=True,
            token=os.environ["HF_TOKEN"],
            cache_dir="/root/models",
        )

        # 2. Load Artist (Flux.1 Dev) - BFloat16
        print("[BOOT] Loading Artist (Flux.1 [dev])...")
        self.artist = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-dev",
            torch_dtype=torch.bfloat16,
            token=os.environ["HF_TOKEN"],
            cache_dir="/root/models",
        ).to(self.device)
        self.artist.enable_model_cpu_offload()

        # 3. Load Animator (CogVideoX-5B) - BFloat16
        print("[BOOT] Loading Animator (CogVideoX-5B)...")
        self.animator = CogVideoXImageToVideoPipeline.from_pretrained(
            "THUDM/CogVideoX-5b-I2V",
            torch_dtype=torch.bfloat16,
            token=os.environ["HF_TOKEN"],
            cache_dir="/root/models",
        ).to(self.device)
        self.animator.enable_model_cpu_offload()

    def analyze_audio(self, audio_path):
        """Extracts word-level timestamps"""
        import whisperx
        import torch

        print(f"[EARS] Transcribing {audio_path}...")
        model = whisperx.load_model("large-v2", self.device, compute_type="float16")
        audio = whisperx.load_audio(audio_path)
        result = model.transcribe(audio, batch_size=16)

        del model
        torch.cuda.empty_cache()
        return result["segments"]

    def generate_storyboard(self, segments, title, tags):
        """Generates the cinematic script using Llama 3.1"""
        lyrics_text = "\n".join(
            [f"[{s['start']:.2f}-{s['end']:.2f}] {s['text']}" for s in segments]
        )

        user_prompt = f"""
        Song Title: "{title}"
        Genre/Tags: {tags}
        
        Lyrics:
        {lyrics_text[:3000]}
        
        INSTRUCTIONS:
        1. Define a 'Visual Style' string (e.g., "Cinematic, 35mm film, cyberpunk neon, grainy").
        2. Define a 'Protagonist' string (e.g., "A lone robot with a cracked screen").
        3. For every lyric segment, create a scene that includes the Protagonist + Visual Style.
        """

        messages = [
            {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        input_ids = self.tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt"
        ).to(self.device)

        outputs = self.director.generate(
            input_ids, max_new_tokens=2500, temperature=0.7
        )
        response = self.tokenizer.decode(
            outputs[0][input_ids.shape[-1] :], skip_special_tokens=True
        )

        try:
            start = response.find("[")
            end = response.rfind("]") + 1
            json_str = response[start:end]
            return json.loads(json_str)
        except Exception as e:
            print(f"[ERROR] JSON Parse Fail: {e}")
            return [
                {
                    "start": 0,
                    "end": 5,
                    "visual_prompt": f"Abstract art representing {title}",
                    "motion_prompt": "Slow pan right",
                }
            ]

    @modal.method()
    def create_music_video(self, audio_url: str, title: str, tags: str, video_id: str):
        import requests
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
        from diffusers.utils.export_utils import export_to_video

        # 1. Download
        print(f"[START] Processing: {title}")
        audio_path = f"/tmp/assets/{video_id}.mp3"
        with open(audio_path, "wb") as f:
            f.write(requests.get(audio_url).content)

        # 2. Analyze
        segments = self.analyze_audio(audio_path)

        # 3. Storyboard
        print("[MIND] Director is writing the script...")
        storyboard = self.generate_storyboard(segments, title, tags)

        clips = []

        # 4. Generate
        for i, scene in enumerate(storyboard):
            duration = scene.get("end", 0) - scene.get("start", 0)
            if duration < 2:
                continue

            print(f"[SCENE {i + 1}] {scene['visual_prompt'][:50]}...")

            # A. Flux
            image = self.artist(
                prompt=scene["visual_prompt"],
                height=768,
                width=1360,
                num_inference_steps=25,
                guidance_scale=3.5,
            ).images[0]

            # B. CogVideoX
            frames = self.animator(
                prompt=scene["motion_prompt"],
                image=image,
                num_frames=49,
                num_inference_steps=50,
                guidance_scale=6.0,
            ).frames[0]

            # C. Export
            scene_path = f"/tmp/assets/{video_id}_scene_{i}.mp4"
            export_to_video(frames, scene_path, fps=8)

            # D. Loop
            clip = VideoFileClip(scene_path)
            if clip.duration < duration:
                clip = clip.loop(duration=duration)
            else:
                clip = clip.subclip(0, duration)
            clips.append(clip)

        # 5. Final Stitch
        print("[EDIT] Stitching master...")
        final_video = concatenate_videoclips(clips, method="compose")
        audio_track = AudioFileClip(audio_path)
        final_video = final_video.set_audio(audio_track)

        output_path = f"/tmp/assets/{video_id}_master.mp4"
        final_video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=24,
            preset="medium",
            bitrate="8000k",
        )

        with open(output_path, "rb") as f:
            return f.read()


# ==============================================================================
# 🌐 N8N INTEGRATION POINT
# ==============================================================================
@app.function(
    image=image,  # Uses the image with fastapi[standard]
    timeout=3600,
)
@modal.fastapi_endpoint(method="POST")
def n8n_webhook(data: dict):
    """
    HTTP Entrypoint for n8n.
    Receives JSON -> Triggers A100 Job -> Returns MP4 File
    """
    print(f"[WEBHOOK] Received request for: {data.get('title', 'Unknown')}")

    factory = VideoFactory()

    try:
        # Trigger the remote GPU job
        video_bytes = factory.create_music_video.remote(
            audio_url=data["audio_url"],
            title=data.get("title", "Unknown Song"),
            tags=data.get("tags", "Music"),
            video_id=data.get("video_id", "suno_video"),
        )

        # Return video file directly
        return modal.Response(
            content=video_bytes,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename={data.get('video_id')}.mp4"
            },
        )
    except Exception as e:
        print(f"[ERROR] Generation failed: {e}")
        return modal.Response(
            content=json.dumps({"error": str(e)}).encode("utf-8"),
            status_code=500,
            media_type="application/json",
        )


# ==============================================================================
# 🧪 LOCAL TESTING
# ==============================================================================
@app.local_entrypoint()
def main():
    print("🧪 Starting local test...")
    factory = VideoFactory()
    video_bytes = factory.create_music_video.remote(
        audio_url="https://cdn1.suno.ai/example.mp3",  # Replace with real MP3 for test
        title="Test Run v3.1",
        tags="Synthwave, Cyberpunk",
        video_id="test_run_v3",
    )
    with open("test_output_v3.mp4", "wb") as f:
        f.write(video_bytes)
    print("✅ Test complete! Video saved to test_output_v3.mp4")
