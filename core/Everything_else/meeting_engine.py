# [meeting_engine.py]

import os, sys, gc, queue, time, subprocess, re
import sounddevice as sd
import scipy.io.wavfile as wav
import numpy as np
import whisper
import torch
from PySide6.QtCore import QThread, Signal

from Everything_else.model_registry import load_model_from_config, unload_previous_model
from core.paths import MODELS_DIR, USER_DATA 

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

class MeetingWorker(QThread):
    status_signal = Signal(str)
    progress_signal = Signal(int)
    result_signal = Signal(str)

    def __init__(self, custom_name=None, engine=None, manifest=None, mode="record"):
        super().__init__()
        self.engine = engine
        self.manifest = manifest
        self.mode = mode 
        self.sample_rate = 16000
        self.recording_queue = queue.Queue()
        self.is_running = True
        self.recordings_dir = os.path.join(USER_DATA, "recordings")
        
        # Define base name and paths
        raw_alias = str(custom_name) if custom_name else "session"    
        self.base_name = re.sub(r'[^\w\s-]', '', raw_alias).strip().replace(" ", "_")
        self.audio_path = os.path.join(self.recordings_dir, f"{self.base_name}.wav")
        self.report_path = os.path.join(self.recordings_dir, f"report_{self.base_name}.html")

    def stop_recording(self):
        self.is_running = False

    def run(self):
        unload_previous_model()
        gc.collect()

        if self.mode == "record":
            self.run_recording_logic()
        else:
            self.run_analysis_logic()

    def run_recording_logic(self):
        self.status_signal.emit("MIC ACTIVE: RECORDING...")
        self.progress_signal.emit(5)
        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, callback=self.callback):
                while self.is_running:
                    self.msleep(100)
        except Exception as e:
            self.status_signal.emit(f"Hardware Error: {e}")
            return

        self.status_signal.emit("PACKING VAULT DATA...")
        audio_data = []
        while not self.recording_queue.empty():
            audio_data.append(self.recording_queue.get())
        
        if not audio_data: return
            
        recorded_audio = np.concatenate(audio_data, axis=0)
        wav.write(self.audio_path, self.sample_rate, recorded_audio)
        
        mp3_path = self.audio_path.replace(".wav", ".mp3")
        ffmpeg_bin = os.path.join(CURRENT_DIR, "ffmpeg.exe")
        
        try:
            # 1. Convert to MP3
            subprocess.run([ffmpeg_bin, "-y", "-i", self.audio_path, "-codec:a", "libmp3lame", "-qscale:a", "2", mp3_path], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # 2. Encrypt Audio
            fid, size = self.engine.encrypt_file(mp3_path)
            self.manifest.add_entry(name=f"{self.base_name}.mp3", id=fid, size=size, file_type=".mp3", folder="Meetings")
            
            # 3. Create and Encrypt Placeholder Report
            with open(self.report_path, "w") as f:
                f.write("<h2 style='color:#ffb000;'>RECORDING SECURED</h2>"
                        "<p>Select the session from the log and click 'ANALYZE' to generate the intelligence brief.</p>")
            
            rid, r_size = self.engine.encrypt_file(self.report_path)
            self.manifest.add_entry(
                name=f"report_{self.base_name}.html.ghost", 
                id=rid, 
                size=r_size, 
                file_type=".html", 
                folder="Meetings"
            )
            
            # 4. Cleanup local files
            for p in [mp3_path, self.audio_path, self.report_path]:
                if os.path.exists(p): os.remove(p)

        except Exception as e:
            print(f"Vault encryption failed: {e}")
            self.status_signal.emit("ENCRYPTION ERROR")

        self.progress_signal.emit(100)
        self.status_signal.emit("AUDIO SECURED IN VAULT")
        self.result_signal.emit("RECORDING_COMPLETE")

    def run_analysis_logic(self):
        self.status_signal.emit("DECRYPTING FROM VAULT...")
        self.progress_signal.emit(10)
        try:
            files = self.manifest.get_files()
            target = next((f for f in files if f['name'] == f"{self.base_name}.mp3"), None)
            if not target: raise Exception("Audio not found in vault")
            
            audio_data = self.engine.decrypt_file_to_memory(target['id'])
            temp_mp3 = os.path.join(self.recordings_dir, f"temp_{self.base_name}.mp3")
            with open(temp_mp3, "wb") as f: f.write(audio_data)
            
            # 2. Transcribe
            self.status_signal.emit("OLLIE IS TRANSCRIBING...")
            self.progress_signal.emit(35) 
            model = whisper.load_model("large-v3-turbo", download_root=MODELS_DIR)
            result = model.transcribe(temp_mp3, fp16=False)
            full_transcript = result['text']

            # --- CLEAR MEMORY FOR LLM ---
            del model
            if torch.cuda.is_available(): 
                torch.cuda.empty_cache() 
            gc.collect() 

            # 3. Analyze / Synthesis
            self.progress_signal.emit(75) 
            self.status_signal.emit("OLLIE IS SYNTHESIZING...")
            
            # Use the correct identifier and unpack the 2-tuple return
            jynx_fn, _ = load_model_from_config("jynx_default") 
            
            prompt = f"Summarize this meeting transcript and extract action items:\n\n{full_transcript}"
            
            # Call the function directly as you did in the working version
            raw_response = jynx_fn(prompt, stream_override=False) 
            
            if isinstance(raw_response, dict) and 'choices' in raw_response:
                full_analysis = raw_response['choices'][0]['text'].strip()
            else:
                full_analysis = str(raw_response).strip()
            
            report_html = self.format_report(full_transcript, full_analysis)
            
            # --- VAULT STORAGE FOR SUMMARY ---
            temp_html_path = os.path.join(self.recordings_dir, f"temp_sum_{self.base_name}.html")
            with open(temp_html_path, "w", encoding="utf-8") as f: 
                f.write(report_html)
            
            report_name = f"report_{self.base_name}.html.ghost"
            all_files = self.manifest.get_files()
            old_entry = next((f for f in all_files if f['name'] == report_name), None)
            
            if old_entry:
                self.manifest.remove_entry(old_entry['id'])

            # Now encrypt the real summary
            sid, s_size = self.engine.encrypt_file(temp_html_path)
            self.manifest.add_entry(
                name=report_name, 
                id=sid, 
                size=s_size, 
                file_type=".html", 
                folder="Meetings"
            )

            # CLEANUP: Remove all local traces immediately
            if os.path.exists(temp_mp3): os.remove(temp_mp3)
            if os.path.exists(temp_html_path): os.remove(temp_html_path)

            # Signal the UI with the HTML string directly so it can display it
            self.result_signal.emit(report_html)
            self.status_signal.emit("ANALYSIS COMPLETE • SECURED")
            
        except Exception as e:
            self.result_signal.emit(f"Analysis Failed: {e}")

    def format_report(self, transcript, analysis):
        import datetime
        timestamp = datetime.datetime.now().strftime("%B %d, %Y | %I:%M %p")
        # Clean up the base name for the header
        display_name = self.base_name.replace('_', ' ').upper()
        
        report_css = f"""
        <style>
            body {{ 
                background-color: transparent; 
                color: #e6edf3; 
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; 
                padding: 40px; 
                line-height: 1.6; 
            }}
            .header {{ 
                border-bottom: 1px solid #30363d; 
                padding-bottom: 20px; 
                margin-bottom: 40px; 
            }}
            .protocol-tag {{ 
                color: #8b949e; 
                font-size: 11px; 
                letter-spacing: 2px; 
                font-weight: 600; 
                text-transform: uppercase; 
            }}
            .session-title {{ 
                font-size: 28px; 
                font-weight: 300; 
                color: #ffb000; 
                margin: 10px 0; 
                letter-spacing: -0.5px; 
            }}
            .meta {{ 
                color: #8b949e; 
                font-size: 12px; 
                font-style: italic;
            }}
            .intel-container {{ 
                margin-bottom: 45px; 
            }}
            .section-label {{ 
                color: #ffb000; 
                font-size: 12px; 
                font-weight: 700; 
                text-transform: uppercase; 
                display: block; 
                margin-bottom: 15px;
                letter-spacing: 1px;
            }}
            .analysis-content {{ 
                font-size: 16px; 
                color: #f0f6fc; 
                white-space: pre-wrap; 
                background: #0d1117;
                padding: 20px;
                border-radius: 6px;
                border: 1px solid #21262d;
            }}
            .transcript-zone {{ 
                font-size: 13px; 
                color: #8b949e; 
                padding: 20px; 
                background: rgba(0,0,0,0.2);
                border-radius: 6px;
                line-height: 1.8;
            }}
            b, strong {{ 
                color: #ffb000; 
                font-weight: 600; 
            }} 
            .footer {{
                text-align: center; 
                margin-top: 60px; 
                opacity: 0.4; 
                font-size: 10px; 
                letter-spacing: 2px;
                color: #8b949e;
            }}
        </style>
        """
        
        return f"""
        <html>
        <head>{report_css}</head>
        <body>
            <div class="header">
                <span class="protocol-tag">Internal Intelligence Briefing</span>
                <div class="session-title">{display_name}</div>
                <div class="meta">Generated on {timestamp}</div>
            </div>
            
            <div class="intel-container">
                <span class="section-label">Executive Summary</span>
                <div class="analysis-content">{analysis}</div>
            </div>
            
            <div class="intel-container">
                <span class="section-label">Meeting Transcript</span>
                <div class="transcript-zone">{transcript}</div>
            </div>
            
            <div class="footer">
                OFFLINE ENCRYPTION ACTIVE // GHOSTDRIVE PROTOCOL
            </div>
        </body>
        </html>
        """

    def callback(self, indata, frames, time, status):
        if status: print(status, file=sys.stderr)
        self.recording_queue.put(indata.copy())