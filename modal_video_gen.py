"""
Suno Video Factory v3.5 - "The Production Fix"
Architecture: A100-80GB | Flux.1 [dev] | CogVideoX-5B | Llama 3.1
Critical Fixes:
- Updated to @modal.fastapi_endpoint (fixes deprecation)
- Simplified payload structure (fixes 422 errors)
- Enhanced error logging
- Proper FastAPI integration
"""

import json
import os
import traceback
from typing import Optional

import modal
import requests
from fastapi import HTTPException, Request, Response
from fastapi.responses import StreamingResponse

# ==============================================================================
# 📦 CONFIGURATION & VOLUMES
# ==============================================================================
app = modal.App("suno-video-factory-v3-5-1")

# Shared volumes for model caching
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
4. **Format**: Output ONLY a valid JSON array with this structure:
[
  {
    "start": 0.0,
    "end": 5.2,
    "visual_prompt": "detailed scene description with protagonist and visual style",
    "motion_prompt": "camera movement description"
  }
]
"""

# ==============================================================================
# 🏭 THE FACTORY ENVIRONMENT
# ==============================================================================
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "ffmpeg",
        "git",
        "libglib2.0-0",
        "libsm6",
        "libxext6",
        "libfontconfig1",
        "libxrender1",
        "libx11-6",
        "libxcb1",
        "libxcb-render0",
        "libxcb-shm0",
        "libxcomposite1",
        "libxcursor1",
        "libxdamage1",
        "libxfixes3",
        "libxi6",
        "libxrandr2",
        "libxss1",
        "libxtst6",
    )
    .pip_install(
        "torch==2.4.0",
        "torchvision==0.19.0",
        "torchaudio==2.4.0",
        extra_options="--index-url https://download.pytorch.org/whl/cu121",
    )
    .pip_install(
        "fastapi[standard]",
        "diffusers>=0.35.1",
        "transformers>=4.44.0",
        "accelerate>=0.34.0",
        "sentencepiece",
        "moviepy>=2.0.0",
        "imageio-ffmpeg>=0.5.1",
        "bitsandbytes",
        "whisperx>=3.1.1",
        "opencv-python-headless",
        "numpy<2.0.0",
        "psycopg2-binary",
        "cloudinary",
    )
    .pip_install(
        "torch==2.4.0",
        "torchvision==0.19.0",
        "torchaudio==2.4.0",
        extra_options="--index-url https://download.pytorch.org/whl/cu121",
    )
    .pip_install(
        "fastapi[standard]",
        "diffusers>=0.35.1",
        "transformers>=4.44.0",
        "accelerate>=0.34.0",
        "sentencepiece",
        "moviepy>=2.0.0",
        "imageio-ffmpeg>=0.5.0",
        "bitsandbytes",
        "whisperx>=3.1.1",
        "opencv-python-headless",
        "numpy<2.0.0",
    )
)


@app.cls(
    image=image,
    gpu="A100-80GB",
    timeout=3600,
    volumes={"/root/models": model_volume, "/tmp/assets": asset_volume},
    secrets=[modal.Secret.from_name("suno-video-secrets")],
)
class VideoFactory:
    @modal.enter()
    def enter(self):
        """Zero-Latency Bootstrap: Load all 3 models into VRAM"""
        print("[BOOT] Initializing Factory v3.5...")

        # Set Device inside lifecycle method
        self.device = "cuda"

        import torch
        from diffusers import CogVideoXImageToVideoPipeline
        from diffusers.pipelines.flux.pipeline_flux import FluxPipeline
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.backends.cuda.matmul.allow_tf32 = True

        # Load Director (Llama 3.1 8B)
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

        # Load Artist (Flux.1 Dev)
        print("[BOOT] Loading Artist (Flux.1 [dev])...")
        self.artist = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-dev",
            torch_dtype=torch.bfloat16,
            token=os.environ["HF_TOKEN"],
            cache_dir="/root/models",
        ).to(self.device)
        self.artist.enable_model_cpu_offload()

        # Load Animator (CogVideoX-5B)
        print("[BOOT] Loading Animator (CogVideoX-5B)...")
        self.animator = CogVideoXImageToVideoPipeline.from_pretrained(
            "THUDM/CogVideoX-5b-I2V",
            torch_dtype=torch.bfloat16,
            token=os.environ["HF_TOKEN"],
            cache_dir="/root/models",
        ).to(self.device)
        self.animator.enable_model_cpu_offload()

        print("[BOOT] Checking moviepy...")
        try:
            import moviepy

            print("[BOOT] moviepy imported successfully")
        except ImportError as e:
            print(f"[BOOT] moviepy import failed: {e}")

        # Configure Cloudinary
        import cloudinary

        cloudinary.config(
            cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
            api_key=os.environ["CLOUDINARY_API_KEY"],
            api_secret=os.environ["CLOUDINARY_API_SECRET"],
        )
        print("[BOOT] Cloudinary configured.")

        print("[BOOT] Factory Ready.")

    def analyze_audio(self, audio_path: str) -> list:
        """Transcribe audio using WhisperX"""
        import torch
        import whisperx

        print(f"[EARS] Transcribing {audio_path}...")

        model = whisperx.load_model("large-v2", self.device, compute_type="float16")
        audio = whisperx.load_audio(audio_path)
        result = model.transcribe(audio, batch_size=16)

        del model
        torch.cuda.empty_cache()

        return result.get("segments", [])

    def generate_storyboard(self, segments: list, title: str, tags: str) -> list:
        """Use Llama 3.1 to generate cinematic storyboard"""

        # Build lyrics text from segments
        lyrics_text = "\n".join(
            [f"[{s['start']:.2f}-{s['end']:.2f}] {s['text']}" for s in segments]
        )

        user_prompt = f"""
Song Title: "{title}"
Genre/Tags: {tags}

Lyrics (with timestamps):
{lyrics_text[:3000]}

TASK: Create a cinematic storyboard as a JSON array. Each scene must:
- Include the Visual Style and Protagonist consistently
- Specify timing (start/end in seconds)
- Provide detailed visual_prompt
- Provide motion_prompt for camera movement

Output ONLY the JSON array, no other text.
        """

        messages = [
            {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        input_ids = self.tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt"
        ).to(self.device)

        outputs = self.director.generate(
            input_ids, max_new_tokens=2500, temperature=0.7, do_sample=True
        )

        response = self.tokenizer.decode(
            outputs[0][input_ids.shape[-1] :], skip_special_tokens=True
        )

        # Extract JSON from response
        try:
            start = response.find("[")
            end = response.rfind("]") + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON array found in response")

            json_str = response[start:end]
            storyboard = json.loads(json_str)

            print(f"[MIND] Generated {len(storyboard)} scenes")
            return storyboard

        except Exception as e:
            print(f"[ERROR] JSON Parse Failed: {e}")
            print(f"[DEBUG] Raw response: {response[:500]}")
            # Fallback: create simple scene
            return [
                {
                    "start": 0.0,
                    "end": 10.0,
                    "visual_prompt": f"{title} - Cinematic music video scene",
                    "motion_prompt": "Slow pan across scene",
                }
            ]

    @modal.method()
    def create_music_video(
        self, audio_url: str, title: str, tags: str, suno_id: str
    ) -> bytes:
        """
        Main video generation pipeline

        Args:
            audio_url: URL to download audio from
            title: Song title
            tags: Genre/style tags
            suno_id: Unique identifier for this song

        Returns:
            Video file as bytes
        """
        import torch
        from diffusers.utils.export_utils import export_to_video
        from moviepy import (
            AudioFileClip,
            VideoFileClip,
            concatenate_videoclips,
        )

        # Prepare Cloudinary folder
        import re

        folder_name = re.sub(r"[^\w\-_\. ]", "_", title).replace(" ", "_")
        song_folder = f"{folder_name}_{suno_id}"

        print(f"[START] Processing: {title} ({suno_id})")

        # Ensure asset directory exists
        os.makedirs("/tmp/assets", exist_ok=True)

        # Download audio
        audio_path = f"/tmp/assets/{suno_id}.mp3"
        if not os.path.exists(audio_path):
            print(f"[DOWNLOAD] Fetching audio from {audio_url}")
            response = requests.get(audio_url, timeout=30)
            response.raise_for_status()
            with open(audio_path, "wb") as f:
                f.write(response.content)
            print(f"[DOWNLOAD] Audio saved: {len(response.content)} bytes")

        # Analyze audio
        segments = self.analyze_audio(audio_path)
        if not segments:
            raise ValueError("Audio transcription returned no segments")

        # Generate storyboard
        print("[MIND] Director is writing the script...")
        storyboard = self.generate_storyboard(segments, title, tags)

        if not storyboard:
            raise ValueError("Storyboard generation failed")

        # Generate video clips
        clips = []
        for i, scene in enumerate(storyboard):
            duration = scene.get("end", 0) - scene.get("start", 0)

            # Skip very short scenes
            if duration < 2:
                print(f"[SKIP] Scene {i + 1} too short ({duration}s)")
                continue

            print(
                f"[SCENE {i + 1}/{len(storyboard)}] Generating: {scene.get('visual_prompt', '')[:60]}..."
            )

            # Generate image with Flux
            image = self.artist(
                prompt=scene.get("visual_prompt", title),
                height=768,
                width=1360,
                num_inference_steps=25,
                guidance_scale=3.5,
            ).images[0]

            # Upload image to Cloudinary
            import io

            img_buffer = io.BytesIO()
            image.save(img_buffer, format="PNG")
            img_buffer.seek(0)
            import cloudinary.uploader

            upload_result = cloudinary.uploader.upload(
                img_buffer, folder=f"{song_folder}/images", public_id=f"scene_{i}"
            )
            scene["image_url"] = upload_result["secure_url"]
            print(f"[UPLOAD] Image uploaded: {scene['image_url']}")

            # Animate with CogVideoX
            frames = self.animator(
                prompt=scene.get("motion_prompt", "Slow pan"),
                image=image,
                num_frames=49,
                num_inference_steps=50,
                guidance_scale=6.0,
            ).frames[0]

            # Export scene
            scene_path = f"/tmp/assets/{suno_id}_scene_{i}.mp4"
            export_to_video(frames, scene_path, fps=8)

            # Upload scene video to Cloudinary
            import cloudinary.uploader

            upload_result = cloudinary.uploader.upload(
                scene_path,
                folder=f"{song_folder}/scene_videos",
                public_id=f"scene_{i}",
                resource_type="video",
            )
            scene["video_url"] = upload_result["secure_url"]
            print(f"[UPLOAD] Scene video uploaded: {scene['video_url']}")

            # Load and adjust duration
            clip = VideoFileClip(scene_path)
            if clip.duration < duration:
                n = int(duration / clip.duration) + 1
                clip = concatenate_videoclips([clip] * n).subclipped(0, duration)
            else:
                clip = clip.subclipped(0, duration)

            clips.append(clip)

            # Clear CUDA cache
            torch.cuda.empty_cache()

        if not clips:
            raise ValueError("No clips were generated")

        # Stitch together final video
        print(f"[EDIT] Stitching {len(clips)} clips into master...")
        final_video = concatenate_videoclips(clips, method="compose")

        # Add audio track
        audio_track = AudioFileClip(audio_path)
        final_video = final_video.with_audio(audio_track)

        # Export final video
        output_path = f"/tmp/assets/{suno_id}_master.mp4"
        final_video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=24,
            preset="medium",
            bitrate="8000k",
            threads=4,
        )

        # Read video bytes
        with open(output_path, "rb") as f:
            video_bytes = f.read()

        print(f"[SUCCESS] Video generated: {len(video_bytes)} bytes")

        # Upload final video to Cloudinary
        import cloudinary.uploader

        upload_result = cloudinary.uploader.upload(
            video_bytes,
            folder=f"{song_folder}/final_video",
            public_id="final",
            resource_type="video",
        )
        final_video_url = upload_result["secure_url"]
        print(f"[UPLOAD] Final video uploaded: {final_video_url}")

        # Cleanup
        for clip in clips:
            clip.close()
        final_video.close()
        audio_track.close()

        # Save to database
        try:
            import psycopg2

            conn = psycopg2.connect(os.environ["DATABASE_URL"])
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS generations (
                    id SERIAL PRIMARY KEY,
                    suno_id TEXT UNIQUE,
                    title TEXT,
                    tags TEXT,
                    audio_url TEXT,
                    segments JSON,
                    storyboard JSON,
                    final_video_url TEXT,
                    status TEXT DEFAULT 'processing',
                    processing_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processing_completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute(
                "INSERT INTO generations (suno_id, title, tags, audio_url, segments, storyboard, final_video_url) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (suno_id) DO UPDATE SET title = EXCLUDED.title, tags = EXCLUDED.tags, audio_url = EXCLUDED.audio_url, segments = EXCLUDED.segments, storyboard = EXCLUDED.storyboard, final_video_url = EXCLUDED.final_video_url",
                (
                    suno_id,
                    title,
                    tags,
                    audio_url,
                    json.dumps(segments),
                    json.dumps(storyboard),
                    final_video_url,
                ),
            )
            cur.execute(
                "UPDATE generations SET status = 'completed', processing_completed_at = CURRENT_TIMESTAMP WHERE suno_id = %s",
                (suno_id,),
            )
            conn.commit()
            cur.close()
            conn.close()
            print("[DB] Saved generation metadata to PostgreSQL")
        except Exception as db_e:
            print(f"[DB] Failed to save to DB: {db_e}")

        return video_bytes


# ==============================================================================
# 🌐 N8N INTEGRATION ENDPOINT (CRITICAL FIX v3.5)
# ==============================================================================
@app.function(
    image=image,
    timeout=3600,
)
@modal.fastapi_endpoint(method="POST")  # FIXED: Changed from @modal.web_endpoint
async def n8n_webhook(request: Request):
    """
    N8N webhook endpoint with flexible payload parsing

    Accepts either:
    1. Direct flat structure: {"id": "...", "title": "...", "audio_url": "..."}
    2. n8n wrapped structure: {"body": {"id": "...", ...}}
    3. Double wrapped: {"body": {"body": {"id": "...", ...}}}
    """
    print("=" * 80)
    print(f"[WEBHOOK v3.5] Incoming request")

    try:
        # Parse raw JSON
        raw_payload = await request.json()

        print(f"[DEBUG] Raw payload keys: {list(raw_payload.keys())}")
        print(f"[DEBUG] Raw payload (first 500 chars): {str(raw_payload)[:500]}")

        # Flexible payload extraction - handle all nesting scenarios
        data = raw_payload

        # If wrapped in 'body', unwrap once
        if "body" in data and isinstance(data["body"], dict):
            print("[DEBUG] Unwrapping first 'body' layer")
            data = data["body"]

            # If double-wrapped, unwrap again
            if "body" in data and isinstance(data["body"], dict):
                print("[DEBUG] Unwrapping second 'body' layer (double nested)")
                data = data["body"]

        # Extract required fields
        suno_id = data.get("id")
        title = data.get("title", "Untitled Song")
        audio_url = data.get("audio_url")
        tags = data.get("tags", "Music Video")

        print(f"[WEBHOOK] Extracted data:")
        print(f"  - ID: {suno_id}")
        print(f"  - Title: {title}")
        print(f"  - Audio URL: {audio_url}")
        print(f"  - Tags: {tags}")
        print("=" * 80)

        # Validate required fields
        if not suno_id:
            raise HTTPException(status_code=400, detail="Missing required field: id")

        if not audio_url:
            raise HTTPException(
                status_code=400, detail="Missing required field: audio_url"
            )

        # Generate video
        factory = VideoFactory()
        video_bytes = factory.create_music_video.remote(
            audio_url=audio_url,
            title=title,
            tags=tags,
            suno_id=suno_id,
        )

        # Return video file
        filename = f"{title.replace(' ', '_')}_{suno_id[:8]}.mp4"

        print(f"[WEBHOOK] Success! Returning {len(video_bytes)} bytes")
        print("=" * 80)

        return Response(
            content=video_bytes,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(video_bytes)),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Video generation failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
        print(f"[ERROR] Traceback:")
        traceback.print_exc()

        raise HTTPException(status_code=500, detail=error_msg)


# ==============================================================================
# 🧪 LOCAL TESTING
# ==============================================================================
@app.local_entrypoint()
def main(
    audio_url: str = "https://cdn1.suno.ai/example.mp3",
    title: str = "Test Song v3.5",
    tags: str = "Synthwave, Cyberpunk",
    suno_id: str = "test_v3_5",
):
    """Local test with dynamic parameters"""
    print("🧪 Starting local test...")
    print(f"Audio URL: {audio_url}")
    print(f"Title: {title}")
    print(f"Tags: {tags}")
    print(f"Suno ID: {suno_id}")

    factory = VideoFactory()
    video_bytes = factory.create_music_video.remote(
        audio_url=audio_url,
        title=title,
        tags=tags,
        suno_id=suno_id,
    )

    with open("test_output_v3_5.mp4", "wb") as f:
        f.write(video_bytes)

    print(f"✅ Test complete! Video saved: {len(video_bytes)} bytes")
