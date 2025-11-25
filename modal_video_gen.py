"""
Suno Video Factory v3.3 - "The Stabilizer"
Architecture: A100-80GB | Flux.1 [dev] | CogVideoX-5B | Llama 3.1
Fixes: CUDA 12.1 Compatibility, Modal Lifecycle Compliance
"""

import json
import os

import modal
import requests
from fastapi import Response

# ==============================================================================
# 📦 CONFIGURATION & VOLUMES
# ==============================================================================
app = modal.App("suno-video-factory-v3-3")

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
4. **Format**: Output ONLY a valid JSON array.
"""

# ==============================================================================
# 🏭 THE FACTORY ENVIRONMENT
# ==============================================================================
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "git")
    .pip_install(
        "torch==2.4.0",
        "torchvision==0.19.0",
        "torchaudio==2.4.0",
        extra_options="--index-url https://download.pytorch.org/whl/cu121",
    )
    .pip_install(
        "fastapi[standard]",
        "diffusers==0.30.0",
        "transformers==4.44.0",
        "accelerate==0.33.0",
        "sentencepiece",
        "moviepy==1.0.3",
        "bitsandbytes",
        "whisperx==3.1.1",
        "opencv-python-headless",
        "numpy",
    )
)


@app.cls(
    image=image,
    gpu="A100-80GB",
    timeout=3600,
    max_containers=1,  # Enforce sequential execution
    volumes={"/root/models": model_volume, "/tmp/assets": asset_volume},
    secrets=[modal.Secret.from_name("suno-video-secrets")],
)
class VideoFactory:
    # REMOVED __init__ to fix DeprecationError

    @modal.enter()
    def enter(self):
        """Zero-Latency Bootstrap: Load all 3 models into VRAM"""
        print("[BOOT] Initializing Factory...")

        # 1. Set Device inside lifecycle method (Fixes AttributeError)
        self.device = "cuda"

        import torch
        from diffusers.pipelines.cogvideo.pipeline_cogvideox_image2video import (
            CogVideoXImageToVideoPipeline,
        )
        from diffusers.pipelines.flux.pipeline_flux import FluxPipeline
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.backends.cuda.matmul.allow_tf32 = True

        # 2. Load Director (Llama 3.1 8B)
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

        # 3. Load Artist (Flux.1 Dev)
        print("[BOOT] Loading Artist (Flux.1 [dev])...")
        self.artist = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-dev",
            torch_dtype=torch.bfloat16,
            token=os.environ["HF_TOKEN"],
            cache_dir="/root/models",
        ).to(self.device)
        self.artist.enable_model_cpu_offload()

        # 4. Load Animator (CogVideoX-5B)
        print("[BOOT] Loading Animator (CogVideoX-5B)...")
        self.animator = CogVideoXImageToVideoPipeline.from_pretrained(
            "THUDM/CogVideoX-5b-I2V",
            torch_dtype=torch.bfloat16,
            token=os.environ["HF_TOKEN"],
            cache_dir="/root/models",
        ).to(self.device)
        self.animator.enable_model_cpu_offload()
        print("[BOOT] Factory Ready.")

    def analyze_audio(self, audio_path):
        import torch
        import whisperx

        print(f"[EARS] Transcribing {audio_path}...")
        # Ensure device is set (redundant check)
        if not hasattr(self, "device"):
            self.device = "cuda"

        model = whisperx.load_model("large-v2", self.device, compute_type="float16")
        audio = whisperx.load_audio(audio_path)
        result = model.transcribe(audio, batch_size=16)

        del model
        torch.cuda.empty_cache()
        return result["segments"]

    def generate_storyboard(self, segments, title, tags):
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
            return []

    @modal.method()
    def create_music_video(self, audio_url: str, title: str, tags: str, video_id: str):
        from diffusers.utils.export_utils import export_to_video
        from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips

        print(f"[START] Processing: {title}")
        os.makedirs("/tmp/assets", exist_ok=True)
        audio_path = f"/tmp/assets/{video_id}.mp3"

        if not os.path.exists(audio_path):
            with open(audio_path, "wb") as f:
                f.write(requests.get(audio_url).content)

        segments = self.analyze_audio(audio_path)
        print("[MIND] Director is writing the script...")
        storyboard = self.generate_storyboard(segments, title, tags)

        clips = []

        for i, scene in enumerate(storyboard):
            duration = scene.get("end", 0) - scene.get("start", 0)
            if duration < 2:
                continue

            print(f"[SCENE {i + 1}] {scene.get('visual_prompt', '')[:50]}...")

            image = self.artist(
                prompt=scene.get("visual_prompt", title),
                height=768,
                width=1360,
                num_inference_steps=25,
                guidance_scale=3.5,
            ).images[0]

            frames = self.animator(
                prompt=scene.get("motion_prompt", "Slow pan"),
                image=image,
                num_frames=49,
                num_inference_steps=50,
                guidance_scale=6.0,
            ).frames[0]

            scene_path = f"/tmp/assets/{video_id}_scene_{i}.mp4"
            export_to_video(frames, scene_path, fps=8)

            clip = VideoFileClip(scene_path)
            if clip.duration < duration:
                clip = clip.loop(duration=duration)
            else:
                clip = clip.subclip(0, duration)
            clips.append(clip)

        if not clips:
            raise ValueError("No clips generated")

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
    image=image,
    timeout=3600,
)
@modal.fastapi_endpoint(method="POST")
def n8n_webhook(data: dict):
    print(f"[WEBHOOK] Received request for: {data.get('title', 'Unknown')}")
    factory = VideoFactory()
    try:
        video_bytes = factory.create_music_video.remote(
            audio_url=data["audio_url"],
            title=data.get("title", "Unknown Song"),
            tags=data.get("tags", "Music"),
            video_id=data.get("video_id", "suno_video"),
        )
        return Response(
            content=video_bytes,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename={data.get('video_id')}.mp4"
            },
        )
    except Exception as e:
        print(f"[ERROR] Generation failed: {e}")
        return Response(
            content=json.dumps({"error": str(e)}),
            status_code=500,
            media_type="application/json",
        )
