import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import pyaudio
import wave
import tempfile
import os
from optimum.intel import OVModelForSpeechSeq2Seq
from transformers import WhisperProcessor, pipeline
import pystray
from PIL import Image, ImageDraw
import keyboard

class WhisperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎙️ Whisper Live Transcription")
        self.root.geometry("600x500")
        self.root.resizable(False, False)

        # Dark mode colors
        self.bg_color = "#1e1e1e"
        self.fg_color = "#e0e0e0"
        self.accent_color = "#2d2d2d"
        self.button_bg = "#3a3a3a"

        # Configure root background
        self.root.configure(bg=self.bg_color)
        
        # Recording state
        self.is_recording = False
        self.audio_frames = []
        self.stream = None
        self.p = None
        
        # Audio settings
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        
        # System tray
        self.tray_icon = None
        
        # Window close behavior
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Load model
        self.status_text = "Loading Whisper model..."
        self.setup_ui()
        self.setup_tray()
        self.setup_hotkey()
        self.load_model()
    
    def setup_ui(self):
        
        # Title
        title_label = tk.Label(
            self.root, 
            text="🎙️ Whisper Live Transcription",
            font=("Arial", 16, "bold"),
            fg=self.fg_color,
            bg=self.bg_color,
            pady=10
        )
        title_label.pack()
        
        # Hotkey info
        hotkey_label = tk.Label(
            self.root,
            text="Global Hotkey: Ctrl+Shift+Alt+M (toggle) | Ctrl+Shift+Alt+P (copy)",
            font=("Arial", 9, "italic"),
            fg="#888888",
            bg=self.bg_color
        )
        hotkey_label.pack()
        
        # Record button
        self.record_button = tk.Button(
            self.root,
            text="🔴 Start Recording",
            font=("Arial", 14, "bold"),
            bg="#2d6a2d",
            fg="white",
            activebackground="#3d7a3d",
            width=20,
            height=2,
            command=self.toggle_recording,
            cursor="hand2",
            relief=tk.FLAT
        )
        self.record_button.pack(pady=10)
        
        # Transcription display
        transcription_label = tk.Label(
            self.root,
            text="Transcription:",
            font=("Arial", 11, "bold"),
            fg=self.fg_color,
            bg=self.bg_color
        )
        transcription_label.pack(anchor="w", padx=20, pady=(15, 5))
        
        self.transcription_box = scrolledtext.ScrolledText(
            self.root,
            wrap=tk.WORD,
            width=65,
            height=10,
            font=("Consolas", 10),
            bg="#2d2d2d",
            fg="#e0e0e0",
            insertbackground="#e0e0e0",
            relief=tk.FLAT
        )
        self.transcription_box.pack(padx=20, pady=5)
        
        # Button frame
        button_frame = tk.Frame(self.root, bg=self.bg_color)
        button_frame.pack(pady=10)
        
        # Copy button
        self.copy_button = tk.Button(
            button_frame,
            text="📋 Copy",
            font=("Arial", 10),
            bg=self.button_bg,
            fg=self.fg_color,
            activebackground="#4a4a4a",
            command=self.copy_to_clipboard,
            state=tk.DISABLED,
            relief=tk.FLAT
        )
        self.copy_button.pack(side=tk.LEFT, padx=5)
        
        # Clear button
        clear_button = tk.Button(
            button_frame,
            text="🗑️ Clear",
            font=("Arial", 10),
            bg=self.button_bg,
            fg=self.fg_color,
            activebackground="#4a4a4a",
            command=self.clear_transcription,
            relief=tk.FLAT
        )
        clear_button.pack(side=tk.LEFT, padx=5)
        
        # Minimize to tray button
        tray_button = tk.Button(
            button_frame,
            text="⬇️ Minimize",
            font=("Arial", 10),
            bg=self.button_bg,
            fg=self.fg_color,
            activebackground="#4a4a4a",
            command=self.hide_window,
            relief=tk.FLAT
        )
        tray_button.pack(side=tk.LEFT, padx=5)
        
        # Status bar
        self.status_label = tk.Label(
            self.root,
            text=f"Status: {self.status_text}",
            font=("Arial", 9),
            anchor="w",
            bg="#2d2d2d",
            fg=self.fg_color,
            padx=10,
            pady=5
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_tray_image(self):
        """Create icon for system tray"""
        # Create a simple microphone icon
        image = Image.new('RGB', (64, 64), color='white')
        dc = ImageDraw.Draw(image)
        
        # Draw microphone shape
        dc.ellipse([20, 10, 44, 35], fill='black')
        dc.rectangle([28, 30, 36, 45], fill='black')
        dc.rectangle([20, 45, 44, 50], fill='black')
        dc.rectangle([30, 50, 34, 55], fill='black')
        
        return image
    
    def setup_tray(self):
        """Setup system tray icon"""
        icon_image = self.create_tray_image()
        
        menu = pystray.Menu(
            pystray.MenuItem("Show Window", self.show_window),
            pystray.MenuItem("Start/Stop Recording (Ctrl+Shift+Alt+M)", self.toggle_recording),
            pystray.MenuItem("Copy to Clipboard (Ctrl+Shift+Alt+P)", self.copy_to_clipboard_hotkey),
            pystray.MenuItem("Quit", self.quit_app)
        )
        
        self.tray_icon = pystray.Icon(
            "whisper_transcription",
            icon_image,
            "Whisper Transcription",
            menu
        )
        
        # Run tray icon in separate thread
        tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        tray_thread.start()
    
    def setup_hotkey(self):
        """Setup global hotkey (Ctrl+Shift+Alt+M)"""
        try:
            keyboard.add_hotkey('ctrl+shift+alt+m', self.toggle_recording)
            keyboard.add_hotkey('ctrl+shift+alt+p', self.copy_to_clipboard_hotkey)
        except Exception as e:
            print(f"Could not register hotkey: {e}")
    
    def hide_window(self):
        """Hide window to system tray"""
        self.root.withdraw()
    
    def show_window(self, icon=None, item=None):
        """Show window from system tray"""
        self.root.after(0, self.root.deiconify)
    
    def quit_app(self, icon=None, item=None):
        """Quit application completely"""
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()
    
    def load_model(self):
        """Load Whisper model in background thread"""
        def load():
            try:
                self.model = OVModelForSpeechSeq2Seq.from_pretrained(
                    "./whisper-base-openvino",
                    device="GPU.0"
                )
                # Clear all conflicting decoder settings
                self.model.generation_config.forced_decoder_ids = None
                self.model.config.forced_decoder_ids = None
                
                self.processor = WhisperProcessor.from_pretrained("./whisper-base-openvino")
                
                self.pipe = pipeline(
                    "automatic-speech-recognition",
                    model=self.model,
                    tokenizer=self.processor.tokenizer,
                    feature_extractor=self.processor.feature_extractor,
                )
                
                self.update_status("Ready to record! (Ctrl+Shift+Alt+M)")
                self.record_button.config(state=tk.NORMAL)
            except Exception as e:
                self.update_status(f"Error loading model: {str(e)}")
                self.record_button.config(state=tk.DISABLED)
        
        # Disable button while loading
        self.record_button.config(state=tk.DISABLED)
        
        # Load in background
        thread = threading.Thread(target=load, daemon=True)
        thread.start()
    
    def toggle_recording(self):
        """Start or stop recording"""
        # Check if model is loaded
        if not hasattr(self, 'pipe'):
            self.update_status("⚠️ Model still loading, please wait...")
            return
        
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def start_recording(self):
        """Start recording audio"""
        # Don't start if already recording
        if self.is_recording:
            return
    
        # Clear previous transcription when starting new recording
        self.root.after(0, lambda: self.transcription_box.delete("1.0", tk.END))
        self.root.after(0, lambda: self.copy_button.config(state=tk.DISABLED))

        self.is_recording = True
        self.audio_frames = []

        # Update UI
        self.root.after(0, lambda: self.record_button.config(
            text="⏹️ Stop Recording",
            bg="#8b0000"
        ))
        self.update_status("🎤 Recording... Press Ctrl+Shift+Alt+M or click Stop to finish")

        # Start recording in background thread
        def record():
            local_stream = None
            local_p = None
        
            try:
                local_p = pyaudio.PyAudio()
                local_stream = local_p.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    frames_per_buffer=self.CHUNK
                )
            
                # Store references for cleanup
                self.p = local_p
                self.stream = local_stream
        
                while self.is_recording:
                    try:
                        data = local_stream.read(self.CHUNK, exception_on_overflow=False)
                        if self.is_recording:  # Check again before appending
                            self.audio_frames.append(data)
                    except Exception as e:
                        if self.is_recording:  # Only report if we're still trying to record
                            print(f"Read error: {e}")
                        break
            
            except Exception as e:
                self.update_status(f"Recording error: {str(e)}")
                print(f"Recording setup error: {e}")
        
            # Note: We do NOT clean up here anymore - stop_recording() will handle it

        thread = threading.Thread(target=record, daemon=True)
        thread.start()

    def stop_recording(self):
        """Stop recording and transcribe"""
        if not self.is_recording:
            return
    
        # Signal recording to stop
        self.is_recording = False
    
        # Give the recording thread time to finish reading
        import time
        time.sleep(0.3)
    
        # Capture everything we need BEFORE any cleanup
        frames_to_transcribe = self.audio_frames.copy() if self.audio_frames else []
    
        # Capture stream and p references
        stream_to_close = self.stream
        p_to_terminate = self.p
    
        # Clear the instance variables immediately
        self.stream = None
        self.p = None
    
        # Get sample size safely
        try:
            if p_to_terminate:
                sample_size = p_to_terminate.get_sample_size(self.FORMAT)
            else:
                temp_p = pyaudio.PyAudio()
                sample_size = temp_p.get_sample_size(self.FORMAT)
                temp_p.terminate()
        except:
            sample_size = 2  # Default for paInt16
    
        # Now cleanup audio resources using local references
        if stream_to_close:
            try:
                if stream_to_close.is_active():
                    stream_to_close.stop_stream()
                stream_to_close.close()
            except Exception as e:
                print(f"Stream cleanup: {e}")
    
        if p_to_terminate:
            try:
                p_to_terminate.terminate()
            except Exception as e:
                print(f"PyAudio cleanup: {e}")
    
        # Check if we have audio to transcribe
        if not frames_to_transcribe:
            self.update_status("⚠️ No audio recorded!")
            self.root.after(0, lambda: self.record_button.config(
                text="🔴 Start Recording",
                bg="#4CAF50",
                state=tk.NORMAL
            ))
            return
    
        # Update UI
        self.root.after(0, lambda: self.record_button.config(
            text="🔴 Start Recording",
            bg="#2d6a2d",
            state=tk.DISABLED
        ))
        self.update_status("✍️ Transcribing...")
    
        # Transcribe in background thread
        def transcribe():
            temp_path = None
            try:
                # Save to temp file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_path = temp_file.name
            
                # Write WAV file
                wf = wave.open(temp_path, 'wb')
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(sample_size)
                wf.setframerate(self.RATE)
                wf.writeframes(b''.join(frames_to_transcribe))
                wf.close()
            
                # Transcribe
                result = self.pipe(
                    temp_path,
                    return_timestamps=True, #Enable long-form transcription
                    generate_kwargs={"language": "english", "task": "transcribe"}
                )
            
                # Display result
                text = result['text'].strip()
                if text:
                    self.root.after(0, lambda: self.display_transcription(text))
                else:
                    self.update_status("⚠️ No speech detected")
                    self.root.after(0, lambda: self.record_button.config(state=tk.NORMAL))
            
            except Exception as e:
                error_msg = f"Transcription error: {str(e)}"
                self.update_status(error_msg)
                print(f"Full transcription error: {e}")
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda: self.record_button.config(state=tk.NORMAL))
        
            finally:
                # Clean up temp file
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
    
        # Start transcription thread
        thread = threading.Thread(target=transcribe, daemon=True)
        thread.start()
    
    def display_transcription(self, text):
        """Display transcription in text box"""
        self.transcription_box.insert(tk.END, text + "\n\n")
        self.transcription_box.see(tk.END)
        self.copy_button.config(state=tk.NORMAL)
        
        #Auto-copy to clipboard
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

        self.update_status("✅ Transcription complete & on clipboard! (Ctrl+Shift+Alt+M to record again)")
    
    def copy_to_clipboard(self):
        """Copy transcription to clipboard"""
        text = self.transcription_box.get("1.0", tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.update_status("📋 Copied to clipboard!")

    def copy_to_clipboard_hotkey(self):
        """Copy transcription to clipboard via hotkey"""
        text = self.transcription_box.get("1.0", tk.END).strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.update_status("📋 Copied to clipboard! (Ctrl+Shift+Alt+P)")
            # Optional: Show notification if window is hidden
            if not self.root.winfo_viewable() and self.tray_icon:
                self.tray_icon.notify("Copied to clipboard!", text[:100] + "..." if len(text) > 100 else text)
        else:
            self.update_status("⚠️ Nothing to copy!")
    
    def clear_transcription(self):
        """Clear transcription box"""
        self.transcription_box.delete("1.0", tk.END)
        self.copy_button.config(state=tk.DISABLED)
        self.update_status("Ready to record! (Ctrl+Shift+Alt+M)")
    
    def update_status(self, message):
        """Update status bar"""
        self.root.after(0, lambda: self.status_label.config(text=f"Status: {message}"))

def main():
    root = tk.Tk()
    app = WhisperApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()