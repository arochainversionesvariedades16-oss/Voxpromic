codigo_app = '''
import socket
import threading
import math
import numpy as np
from kivy.utils import platform
from kivy.clock import Clock
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.slider import MDSlider
from kivymd.uix.progressbar import MDProgressBar

if platform == 'android':
    from android.permissions import request_permissions, Permission
    from jnius import autoclass
    
    AudioRecord = autoclass('android.media.AudioRecord')
    AudioSource = autoclass('android.media.MediaRecorder$AudioSource')
    AudioFormat = autoclass('android.media.AudioFormat')

class BiquadFilter:
    """Filtro digital IIR nativo en Python/Numpy sin requerir librerías pesadas."""
    def __init__(self, filter_type, freq, srate, q=0.707):
        self.w0 = 2 * math.pi * freq / srate
        self.alpha = math.sin(self.w0) / (2 * q)
        cos_w0 = math.cos(self.w0)

        if filter_type == 'low':
            b0 = (1 - cos_w0) / 2
            b1 = 1 - cos_w0
            b2 = (1 - cos_w0) / 2
        elif filter_type == 'high':
            b0 = (1 + cos_w0) / 2
            b1 = -(1 + cos_w0)
            b2 = (1 + cos_w0) / 2
        else: # band
            b0 = self.alpha
            b1 = 0
            b2 = -self.alpha

        a0 = 1 + self.alpha
        a1 = -2 * cos_w0
        a2 = 1 - self.alpha

        self.b0, self.b1, self.b2 = b0 / a0, b1 / a0, b2 / a0
        self.a1, self.a2 = a1 / a0, a2 / a0
        self.x1 = self.x2 = self.y1 = self.y2 = 0.0

    def process(self, x):
        y = np.zeros_like(x)
        for i in range(len(x)):
            xi = x[i]
            yi = (self.b0 * xi + self.b1 * self.x1 + self.b2 * self.x2
                  - self.a1 * self.y1 - self.a2 * self.y2)
            self.x2, self.x1 = self.x1, xi
            self.y2, self.y1 = self.y1, yi
            y[i] = yi
        return y

class AudioEngine:
    def __init__(self, target_port=5005, rate=44100, blocksize=1024):
        self.target_ip = None
        self.target_port = target_port
        self.rate = rate
        self.blocksize = blocksize
        self.is_running = False
        self.is_muted = False
        
        self.gain_master = 1.0
        self.gain_bass = 1.0
        self.gain_mid = 1.0
        self.gain_treble = 1.0
        self.vu_level = 0.0

        self.flt_low = BiquadFilter('low', 300.0, self.rate)
        self.flt_mid = BiquadFilter('band', 1200.0, self.rate)
        self.flt_high = BiquadFilter('high', 3500.0, self.rate)

    def discover_device(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(2.0)
        try:
            sock.sendto(b"DISCOVER_VOXPRO", ("255.255.255.255", self.target_port))
            data, addr = sock.recvfrom(1024)
            if b"VOXPRO_ACK" in data:
                self.target_ip = addr[0]
                return self.target_ip
        except socket.timeout:
            return None
        finally:
            sock.close()
        return None

    def process_frame(self, raw_pcm):
        audio = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0
        rms = np.sqrt(np.mean(audio**2)) if len(audio) > 0 else 0
        self.vu_level = min(float(rms * 400), 100.0)
        
        if self.is_muted:
            return b'\\x00' * len(raw_pcm)

        low = self.flt_low.process(audio)
        mid = self.flt_mid.process(audio)
        high = self.flt_high.process(audio)

        mixed = (low * self.gain_bass) + (mid * self.gain_mid) + (high * self.gain_treble)
        processed = np.clip(mixed * self.gain_master, -1.0, 1.0)
        return (processed * 32767.0).astype(np.int16).tobytes()

    def start_stream(self):
        self.is_running = True
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if platform == 'android':
            channel_cfg = AudioFormat.CHANNEL_IN_MONO
            audio_format = AudioFormat.ENCODING_PCM_16BIT
            min_buf = AudioRecord.getMinBufferSize(self.rate, channel_cfg, audio_format)
            buf_size = max(min_buf, self.blocksize * 2)
            
            recorder = AudioRecord(AudioSource.MIC, self.rate, channel_cfg, audio_format, buf_size)
            recorder.startRecording()
            pcm_buffer = bytearray(self.blocksize * 2)

            while self.is_running:
                read_bytes = recorder.read(pcm_buffer, 0, len(pcm_buffer))
                if read_bytes > 0:
                    payload = self.process_frame(pcm_buffer[:read_bytes])
                    if self.target_ip:
                        sock.sendto(payload, (self.target_ip, self.target_port))
            
            recorder.stop()
            recorder.release()
        sock.close()

    def stop_stream(self):
        self.is_running = False
        self.vu_level = 0.0

class VoxProApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "DeepPurple"
        self.theme_cls.theme_style = "Dark"
        self.engine = AudioEngine()

        screen = MDScreen()
        card = MDCard(
            orientation="vertical",
            padding="16dp",
            spacing="10dp",
            size_hint=(0.94, 0.94),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            radius=[16]
        )

        card.add_widget(MDLabel(
            text="VOX-PRO WIRELESS",
            font_style="H5",
            halign="center",
            theme_text_color="Primary"
        ))

        self.lbl_status = MDLabel(
            text="Estado: Buscando ESP32...",
            halign="center",
            font_style="Caption",
            theme_text_color="Secondary"
        )
        card.add_widget(self.lbl_status)

        card.add_widget(MDLabel(text="Nivel de Entrada (VU):", font_style="Caption"))
        self.vu_bar = MDProgressBar(value=0, max=100)
        card.add_widget(self.vu_bar)

        self.slider_bass = self._create_slider(card, "Bajos (Low)", 0.0, 2.0, 1.0, self.set_bass)
        self.slider_mid = self._create_slider(card, "Medios (Mid)", 0.0, 2.0, 1.0, self.set_mid)
        self.slider_treble = self._create_slider(card, "Brillo (High)", 0.0, 2.0, 1.0, self.set_treble)

        controls = MDBoxLayout(orientation="horizontal", spacing="12dp", size_hint_y=None, height="50dp")
        self.btn_mute = MDIconButton(icon="microphone", icon_size="32sp", on_release=self.toggle_mute)
        self.btn_action = MDRaisedButton(text="CONECTAR Y TRANSMITIR", size_hint=(1, 1), on_release=self.toggle_stream)
        controls.add_widget(self.btn_mute)
        controls.add_widget(self.btn_action)
        card.add_widget(controls)

        screen.add_widget(card)

        Clock.schedule_interval(self.update_ui, 1.0 / 30.0)
        threading.Thread(target=self.auto_discover, daemon=True).start()
        return screen

    def on_start(self):
        if platform == 'android':
            request_permissions([
                Permission.RECORD_AUDIO,
                Permission.INTERNET,
                Permission.ACCESS_NETWORK_STATE
            ])

    def _create_slider(self, parent, label_text, vmin, vmax, vdef, callback):
        box = MDBoxLayout(orientation="vertical", size_hint_y=None, height="45dp")
        lbl = MDLabel(text=f"{label_text}: {vdef:.1f}x", font_style="Caption")
        slider = MDSlider(min=vmin, max=vmax, value=vdef)
        slider.bind(value=lambda inst, val: (callback(val), setattr(lbl, 'text', f"{label_text}: {val:.1f}x")))
        box.add_widget(lbl)
        box.add_widget(slider)
        parent.add_widget(box)
        return slider

    def set_bass(self, v): self.engine.gain_bass = v
    def set_mid(self, v): self.engine.gain_mid = v
    def set_treble(self, v): self.engine.gain_treble = v

    def auto_discover(self):
        ip = self.engine.discover_device()
        if ip:
            Clock.schedule_once(lambda dt: setattr(self.lbl_status, 'text', f"Conectado a ESP32: {ip}"))
        else:
            self.engine.target_ip = "192.168.4.1"
            Clock.schedule_once(lambda dt: setattr(self.lbl_status, 'text', "Modo directo: 192.168.4.1"))

    def toggle_mute(self, instance):
        self.engine.is_muted = not self.engine.is_muted
        if self.engine.is_muted:
            self.btn_mute.icon = "microphone-off"
            self.btn_mute.theme_text_color = "Error"
        else:
            self.btn_mute.icon = "microphone"
            self.btn_mute.theme_text_color = "Primary"

    def toggle_stream(self, instance):
        if not self.engine.is_running:
            self.btn_action.text = "DETENER TRANSMISIÓN"
            self.btn_action.md_bg_color = (0.85, 0.2, 0.2, 1)
            threading.Thread(target=self.engine.start_stream, daemon=True).start()
        else:
            self.engine.stop_stream()
            self.btn_action.text = "CONECTAR Y TRANSMITIR"
            self.btn_action.md_bg_color = self.theme_cls.primary_color

    def update_ui(self, dt):
        self.vu_bar.value = self.engine.vu_level

if __name__ == "__main__":
    VoxProApp().run()
'''

with open("main.py", "w") as f:
    f.write(codigo_app)

print("✅ main.py actualizado.")
