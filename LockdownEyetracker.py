import cv2
import mediapipe as mp
import numpy as np
import pydirectinput
import threading
import tkinter as tk
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
from tkinter import messagebox
from PIL import Image, ImageTk
import time
import platform
import logging
import os
import queue

if platform.system() == "Windows":
    try:
        from pygrabber.dshow_graph import FilterGraph
        PYGRABBER_AVAILABLE = True
        logging.info("pygrabber gefunden. Versuche, Kameranamen via DirectShow zu lesen.")
    except ImportError:
        PYGRABBER_AVAILABLE = False
        logging.warning("pygrabber nicht gefunden (pip install pygrabber). Fallback auf generische Kameranamen.")
else:
    PYGRABBER_AVAILABLE = False
    logging.info("Nicht-Windows-System erkannt. Verwende generische Kameranamen.")

mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
face_mesh = None

log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, "eye_tracker_log.txt")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logging.info("--- Eye Tracker Application Started ---")

DEFAULT_EAR_CLOSE = 0.17
DEFAULT_EAR_OPEN = 0.22
DEFAULT_CAM_WIDTH = 320
DEFAULT_CAM_HEIGHT = 240
DEFAULT_CAM_FPS = 30
DEFAULT_PROCESS_INTERVAL = 1
PREVIEW_UPDATE_DELAY_MS = 33

GUI_PREVIEW_WIDTH = 640
GUI_PREVIEW_HEIGHT = 480
GUI_MIN_HEIGHT_NO_PREVIEW = 320
GUI_PREVIEW_FRAME_BUFFER = 45

LEFT_EAR_IDX = [362, 385, 387, 263, 373, 380]
RIGHT_EAR_IDX= [33, 160, 158, 133, 153, 144]

def calculate_ear(eye_landmarks_pixels):
    try:
        p1, p2, p3, p4, p5, p6 = eye_landmarks_pixels
        vertical1 = np.linalg.norm(p2 - p6); vertical2 = np.linalg.norm(p3 - p5)
        horizontal = np.linalg.norm(p1 - p4)
        if horizontal < 1e-6: return 0.0
        ear = (vertical1 + vertical2) / (2.0 * horizontal)
        return max(0.0, ear)
    except (IndexError, ValueError, TypeError):
        return 0.0

def get_directshow_camera_names():
    devices = []
    if not PYGRABBER_AVAILABLE: return devices
    try:
        graph = FilterGraph(); devices = graph.get_input_devices(); del graph
        logging.info(f"DirectShow Geräte gefunden: {devices}")
        return devices
    except Exception as e:
        logging.error(f"Fehler beim Abrufen der DirectShow-Geräte mit pygrabber: {e}", exc_info=False)
        return []

def find_available_cameras(max_cameras_to_check=5):
    cam_generic_name = EyeTrackerApp.translations[EyeTrackerApp.current_language].get('cam_generic_name', "Kamera {}")

    available_cameras = {}
    camera_names_dshow = get_directshow_camera_names()
    logging.info("Suche nach verfügbaren Kameras...")
    for i in range(max_cameras_to_check):
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
        cap = cv2.VideoCapture(i, backend)
        if not cap.isOpened(): cap = cv2.VideoCapture(i)
        if cap.isOpened():
            display_name = cam_generic_name.format(i)
            if i < len(camera_names_dshow) and camera_names_dshow[i]:
                display_name = camera_names_dshow[i].strip()
                logging.info(f"  Gefunden: '{display_name}' (Index {i}, via DirectShow).")
            else:
                logging.info(f"  Gefunden: '{display_name}' (Index {i}, generisch).")
            original_display_name = display_name; count = 1
            while display_name in available_cameras:
                 display_name = f"{original_display_name} ({count})"; count += 1
            available_cameras[display_name] = i
            cap.release()
        else:
            if i > 0 and not available_cameras: break
            elif i >= 2 and not available_cameras: break
    logging.info(f"Gefundene Kameras (Anzeigename -> Index): {available_cameras}")
    if platform.system() == "Windows":
        logging.info("Hinweis: Für Spiel-Interaktion Skript/EXE evtl. 'Als Administrator ausführen'.")
    return available_cameras


class EyeTrackerApp:
    translations = {
        'de': {
            'camera_label': "Kamera:",
            'no_camera_found': "Keine Kamera",
            'start_button': "▶ Start",
            'stop_button': "■ Stop",
            'exit_button': "❌ Exit",
            'preview_frame_title': " Vorschau ",
            'image_error': "Bildfehler",
            'eye_status_frame_title': " Augenstatus ",
            'left_eye_status_initial': "Links: ---",
            'right_eye_status_initial': "Rechts: ---",
            'options_frame_title': " Optionen ",
            'preview_toggle_button': "Vorschau",
            'overlay_checkbutton': "Overlay",
            'advanced_settings_button_tooltip': "Erweiterte Einstellungen",
            'advanced_frame_title': " Erweiterte Einstellungen ",
            'ear_close_label': "EAR Schließen:",
            'ear_open_label': "EAR Öffnen:",
            'cam_width_label': "Kamera Breite:",
            'cam_height_label': "Kamera Höhe:",
            'cam_fps_label': "Kamera FPS (Ziel):",
            'process_interval_label': "Frame Intervall:",
            'apply_settings_button': "Anwenden & Schließen",
            'language_label': "Sprache:",
            'cam_generic_name': "Kamera {}",
            'left_eye_status_prefix': "Links:",
            'right_eye_status_prefix': "Rechts:",
            'searching_face': "Suche Gesicht...",
            'status_closed': "GESCHLOSSEN",
            'status_open': "OFFEN",
            'ear_label': "EAR:",
            'no_camera_alert_title': "Keine Kamera",
            'no_camera_alert_text': "Keine Kamera gefunden. Anwendung funktioniert möglicherweise nicht.",
            'settings_error_title': "Fehler bei Einstellungen",
            'settings_error_prefix': "Einige Eingaben waren ungültig:\n\n",
            'settings_applied_title': "Einstellungen angewendet",
            'settings_applied_text': "Einstellungen wurden übernommen.",
            'settings_applied_restart_suffix': "\nBitte Tracking/Vorschau neu starten, um Kamera-Änderungen zu aktivieren.",
            'camera_error_title': "Kamerafehler",
            'camera_error_text_template': "Kamera '{}' konnte nicht geöffnet werden.",
            'no_camera_warning_title': "Keine Kamera",
            'no_camera_warning_text': "Bitte Kamera wählen.",
        },
        'en': {
            'camera_label': "Camera:",
            'no_camera_found': "No Camera",
            'start_button': "▶ Start",
            'stop_button': "■ Stop",
            'exit_button': "❌ Exit",
            'preview_frame_title': " Preview ",
            'image_error': "Image Error",
            'eye_status_frame_title': " Eye Status ",
            'left_eye_status_initial': "Left: ---",
            'right_eye_status_initial': "Right: ---",
            'options_frame_title': " Options ",
            'preview_toggle_button': "Preview",
            'overlay_checkbutton': "Overlay",
            'advanced_settings_button_tooltip': "Advanced Settings",
            'advanced_frame_title': " Advanced Settings ",
            'ear_close_label': "EAR Close:",
            'ear_open_label': "EAR Open:",
            'cam_width_label': "Camera Width:",
            'cam_height_label': "Camera Height:",
            'cam_fps_label': "Camera FPS (Target):",
            'process_interval_label': "Frame Interval:",
            'apply_settings_button': "Apply & Close",
            'language_label': "Language:",
            'cam_generic_name': "Camera {}",
            'left_eye_status_prefix': "Left:",
            'right_eye_status_prefix': "Right:",
            'searching_face': "Searching for face...",
            'status_closed': "CLOSED",
            'status_open': "OPEN",
            'ear_label': "EAR:",
            'no_camera_alert_title': "No Camera",
            'no_camera_alert_text': "No camera found. Application might not work.",
            'settings_error_title': "Settings Error",
            'settings_error_prefix': "Some inputs were invalid:\n\n",
            'settings_applied_title': "Settings Applied",
            'settings_applied_text': "Settings have been applied.",
            'settings_applied_restart_suffix': "\nPlease restart tracking/preview to activate camera changes.",
            'camera_error_title': "Camera Error",
            'camera_error_text_template': "Could not open camera '{}'.",
            'no_camera_warning_title': "No Camera",
            'no_camera_warning_text': "Please select a camera.",
        }
    }
    current_language = 'de'

    def __init__(self, root_window: ttkb.Window):
        self.root = root_window
        self.root.title('LockdownEyeProtocol v 1.1.1')
        self.root.minsize(760, 580)
        logging.info("Initialisiere GUI...")

        self.tracking_running = False
        self.preview_running = False
        self.is_closing = False
        self.tracking_thread = None
        self.preview_thread = None
        self.camera_name_to_index = find_available_cameras()
        self.camera_display_names = list(self.camera_name_to_index.keys())
        self.selected_camera_name = tk.StringVar()
        self.selected_camera_index = tk.IntVar(value=-1)
        self.left_eye_closed_state = False
        self.right_eye_closed_state = False
        self.left_ear_value = 0.0
        self.right_ear_value = 0.0
        self.face_detected_status = False
        self.camera_lock = threading.Lock()
        self.frame_queue = queue.Queue(maxsize=1)
        self.x_key_down = False
        self.c_key_down = False
        self.both_were_closed = False
        self.show_overlay_var = tk.BooleanVar(value=True)
        self.show_preview_var = tk.BooleanVar(value=True)
        self.advanced_settings_visible = tk.BooleanVar(value=False)
        self.selected_language = tk.StringVar(value='Deutsch' if self.current_language == 'de' else 'English')

        self.ear_close_var = tk.StringVar(value=str(DEFAULT_EAR_CLOSE))
        self.ear_open_var = tk.StringVar(value=str(DEFAULT_EAR_OPEN))
        self.cam_width_var = tk.StringVar(value=str(DEFAULT_CAM_WIDTH))
        self.cam_height_var = tk.StringVar(value=str(DEFAULT_CAM_HEIGHT))
        self.cam_fps_var = tk.StringVar(value=str(DEFAULT_CAM_FPS))
        self.process_interval_var = tk.StringVar(value=str(DEFAULT_PROCESS_INTERVAL))

        self.apply_initial_settings()

        try: theme_bg = self.root.style.colors.get('bg') or '#303030'
        except: theme_bg = '#303030'
        self.placeholder_bg = theme_bg
        try:
            self.placeholder_image = Image.new('RGB', (GUI_PREVIEW_WIDTH // 2, GUI_PREVIEW_HEIGHT // 2), color=self.placeholder_bg)
            self.placeholder_photo = ImageTk.PhotoImage(self.placeholder_image)
        except Exception as e:
            logging.error(f"Fehler Platzhalter Erstellung: {e}")
            self.placeholder_photo = None

        self._setup_gui()

        self.update_eye_status_display()
        if not self.camera_display_names:
            self.start_button.config(state=DISABLED)
            self.overlay_checkbutton.config(state=DISABLED)
            self.preview_toggle_button.config(state=DISABLED)
            self.advanced_settings_button.config(state=DISABLED)
            if hasattr(self, 'preview_outer_frame'): self.preview_outer_frame.grid_forget()
            mb_title = self.translations[self.current_language].get('no_camera_alert_title', "Keine Kamera")
            mb_text = self.translations[self.current_language].get('no_camera_alert_text', "Keine Kamera gefunden. Anwendung funktioniert möglicherweise nicht.")
            messagebox.showinfo(mb_title, mb_text)
        else:
            logging.info("GUI init -> setze erste Kamera und starte Vorschau (falls aktiviert).")
            first_cam_name = self.camera_display_names[0]
            self.selected_camera_name.set(first_cam_name)
            self.selected_camera_index.set(self.camera_name_to_index.get(first_cam_name, -1))
            if self.show_preview_var.get():
                 if self.selected_camera_index.get() != -1:
                     self.root.after(100, self.toggle_preview)
                 else:
                     logging.error(f"Konnte Index für Kamera '{first_cam_name}' nicht finden.")
                     if hasattr(self, 'preview_outer_frame'): self.preview_outer_frame.grid_forget()
            elif hasattr(self, 'preview_outer_frame'):
                 self.preview_outer_frame.grid_forget()

        logging.info("App Initialisierung abgeschlossen.")
        self.root.after(PREVIEW_UPDATE_DELAY_MS, self.update_preview_from_queue)

    def apply_initial_settings(self):
        self.applied_ear_close = DEFAULT_EAR_CLOSE
        self.applied_ear_open = DEFAULT_EAR_OPEN
        self.applied_cam_width = DEFAULT_CAM_WIDTH
        self.applied_cam_height = DEFAULT_CAM_HEIGHT
        self.applied_cam_fps = DEFAULT_CAM_FPS
        self.applied_process_interval = DEFAULT_PROCESS_INTERVAL
        logging.info("Standard-Einstellungen initial angewendet.")

    def _setup_gui(self):
        lang_texts = self.translations[self.current_language]

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self.main_container = ttkb.Frame(self.root, padding=15)
        self.main_container.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.main_container.columnconfigure(0, weight=1)
        self.main_container.rowconfigure(1, weight=1)

        self.top_control_frame = ttkb.Frame(self.main_container, padding=(0,0,0,10))
        self.top_control_frame.grid(row=0, column=0, sticky="ew")
        self.top_control_frame.columnconfigure(1, weight=1)

        self.cam_label = ttkb.Label(self.top_control_frame, text=lang_texts['camera_label'], width=8, font=(None, 10))
        self.cam_label.grid(row=0, column=0, padx=(0, 8), pady=5, sticky="w")

        no_cam_text = lang_texts['no_camera_found']
        self.camera_combobox = ttkb.Combobox(
            self.top_control_frame, textvariable=self.selected_camera_name, state="readonly",
            values=self.camera_display_names if self.camera_display_names else [no_cam_text],
            bootstyle="primary"
        )
        self.camera_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.camera_combobox.bind("<<ComboboxSelected>>", self.on_camera_select)

        action_frame = ttkb.Frame(self.top_control_frame)
        action_frame.grid(row=0, column=2, padx=(15, 0), sticky="e")
        self.start_button = ttkb.Button(action_frame, text=lang_texts['start_button'], command=self.start_tracking, bootstyle="success-outline", width=8)
        self.start_button.pack(side=LEFT, padx=3)
        self.stop_button = ttkb.Button(action_frame, text=lang_texts['stop_button'], command=self.stop_tracking, state=DISABLED, bootstyle="warning-outline", width=8)
        self.stop_button.pack(side=LEFT, padx=3)
        self.exit_button = ttkb.Button(action_frame, text=lang_texts['exit_button'], command=self.on_close, bootstyle="danger-outline", width=8)
        self.exit_button.pack(side=LEFT, padx=3)

        self.preview_outer_frame = ttkb.Frame(self.main_container, width=GUI_PREVIEW_WIDTH, height=GUI_PREVIEW_HEIGHT)
        self.preview_outer_frame.grid(row=1, column=0, pady=10, sticky="nsew")
        self.preview_outer_frame.grid_propagate(False)
        self.preview_outer_frame.columnconfigure(0, weight=1)
        self.preview_outer_frame.rowconfigure(0, weight=1)
        self.preview_labelframe = ttkb.LabelFrame(self.preview_outer_frame, text=lang_texts['preview_frame_title'], padding=0, bootstyle="secondary")
        self.preview_labelframe.grid(row=0, column=0, sticky="nsew")
        self.preview_labelframe.columnconfigure(0, weight=1); self.preview_labelframe.rowconfigure(0, weight=1)
        self.preview_label = ttkb.Label(self.preview_labelframe, anchor="center", background=self.placeholder_bg)
        self.preview_label.grid(row=0, column=0, sticky="nsew")
        if hasattr(self, 'placeholder_photo') and self.placeholder_photo:
            self.preview_label.config(image=self.placeholder_photo)
        else:
            self.preview_label.config(image='', text=lang_texts['image_error'])

        self.bottom_bar = ttkb.Frame(self.main_container, padding=(0, 10))
        self.bottom_bar.grid(row=2, column=0, pady=(10, 0), sticky="ew")
        self.bottom_bar.columnconfigure(0, weight=1)
        self.bottom_bar.columnconfigure(1, weight=0)

        self.status_frame = ttkb.LabelFrame(self.bottom_bar, text=lang_texts['eye_status_frame_title'], padding=(10, 5), bootstyle=SECONDARY)
        self.status_frame.grid(row=0, column=0, sticky="ew")
        self.status_frame.columnconfigure(0, weight=1); self.status_frame.columnconfigure(1, weight=1)
        self.left_eye_status_label = ttkb.Label(self.status_frame, text=lang_texts['left_eye_status_initial'], anchor="center", padding=(5,2))
        self.left_eye_status_label.grid(row=0, column=0, padx=(0, 5), pady=2, sticky="ew")
        self.right_eye_status_label = ttkb.Label(self.status_frame, text=lang_texts['right_eye_status_initial'], anchor="center", padding=(5,2))
        self.right_eye_status_label.grid(row=0, column=1, padx=(5, 0), pady=2, sticky="ew")

        self.options_frame = ttkb.LabelFrame(self.bottom_bar, text=lang_texts['options_frame_title'], padding=(8, 5), bootstyle=SECONDARY)
        self.options_frame.grid(row=0, column=1, padx=(15, 0), sticky="e")
        self.preview_toggle_button = ttkb.Checkbutton(self.options_frame, text=lang_texts['preview_toggle_button'], variable=self.show_preview_var, bootstyle="success-toolbutton", command=self.toggle_preview)
        self.preview_toggle_button.pack(side=LEFT, padx=(0,5))
        self.overlay_checkbutton = ttkb.Checkbutton(self.options_frame, text=lang_texts['overlay_checkbutton'], variable=self.show_overlay_var, bootstyle="info-toolbutton", state=DISABLED)
        self.overlay_checkbutton.pack(side=LEFT, padx=5)
        self.advanced_settings_button = ttkb.Button(self.options_frame, text="⚙", bootstyle="secondary-outline", command=self._toggle_advanced_settings, width=3)
        self.advanced_settings_button.pack(side=LEFT, padx=(5,0))

        self.language_label = ttkb.Label(self.options_frame, text=lang_texts['language_label'])
        self.language_label.pack(side=LEFT, padx=(10, 2))
        self.language_combobox = ttkb.Combobox(
            self.options_frame, textvariable=self.selected_language,
            values=['Deutsch', 'English'], state='readonly', width=8, bootstyle="secondary"
        )
        self.language_combobox.pack(side=LEFT, padx=(0, 5))
        self.language_combobox.bind("<<ComboboxSelected>>", self._on_language_select)

        self.advanced_frame = ttkb.LabelFrame(self.main_container, text=lang_texts['advanced_frame_title'], padding=(15, 10), bootstyle=SECONDARY)
        self.advanced_frame.columnconfigure(1, weight=1)
        adv_row = 0
        self.ear_close_label_widget = ttkb.Label(self.advanced_frame, text=lang_texts['ear_close_label'], anchor='w')
        self.ear_close_label_widget.grid(row=adv_row, column=0, padx=5, pady=4, sticky="w")
        ear_close_entry = ttkb.Entry(self.advanced_frame, textvariable=self.ear_close_var, width=10)
        ear_close_entry.grid(row=adv_row, column=1, padx=5, pady=4, sticky="ew"); adv_row += 1
        self.ear_open_label_widget = ttkb.Label(self.advanced_frame, text=lang_texts['ear_open_label'], anchor='w')
        self.ear_open_label_widget.grid(row=adv_row, column=0, padx=5, pady=4, sticky="w")
        ear_open_entry = ttkb.Entry(self.advanced_frame, textvariable=self.ear_open_var, width=10)
        ear_open_entry.grid(row=adv_row, column=1, padx=5, pady=4, sticky="ew"); adv_row += 1

        ttk_separator_adv1 = ttkb.Separator(self.advanced_frame, orient=HORIZONTAL)
        ttk_separator_adv1.grid(row=adv_row, column=0, columnspan=2, pady=8, sticky="ew"); adv_row += 1
        self.cam_width_label_widget = ttkb.Label(self.advanced_frame, text=lang_texts['cam_width_label'], anchor='w')
        self.cam_width_label_widget.grid(row=adv_row, column=0, padx=5, pady=4, sticky="w")
        cam_width_entry = ttkb.Entry(self.advanced_frame, textvariable=self.cam_width_var, width=10)
        cam_width_entry.grid(row=adv_row, column=1, padx=5, pady=4, sticky="ew"); adv_row += 1
        self.cam_height_label_widget = ttkb.Label(self.advanced_frame, text=lang_texts['cam_height_label'], anchor='w')
        self.cam_height_label_widget.grid(row=adv_row, column=0, padx=5, pady=4, sticky="w")
        cam_height_entry = ttkb.Entry(self.advanced_frame, textvariable=self.cam_height_var, width=10)
        cam_height_entry.grid(row=adv_row, column=1, padx=5, pady=4, sticky="ew"); adv_row += 1
        self.cam_fps_label_widget = ttkb.Label(self.advanced_frame, text=lang_texts['cam_fps_label'], anchor='w')
        self.cam_fps_label_widget.grid(row=adv_row, column=0, padx=5, pady=4, sticky="w")
        cam_fps_entry = ttkb.Entry(self.advanced_frame, textvariable=self.cam_fps_var, width=10)
        cam_fps_entry.grid(row=adv_row, column=1, padx=5, pady=4, sticky="ew"); adv_row += 1

        ttk_separator_adv2 = ttkb.Separator(self.advanced_frame, orient=HORIZONTAL)
        ttk_separator_adv2.grid(row=adv_row, column=0, columnspan=2, pady=8, sticky="ew"); adv_row += 1
        self.process_interval_label_widget = ttkb.Label(self.advanced_frame, text=lang_texts['process_interval_label'], anchor='w')
        self.process_interval_label_widget.grid(row=adv_row, column=0, padx=5, pady=4, sticky="w")
        process_interval_entry = ttkb.Entry(self.advanced_frame, textvariable=self.process_interval_var, width=10)
        process_interval_entry.grid(row=adv_row, column=1, padx=5, pady=4, sticky="ew"); adv_row += 1
        self.apply_button = ttkb.Button(self.advanced_frame, text=lang_texts['apply_settings_button'], command=self._apply_settings, bootstyle="success")
        self.apply_button.grid(row=adv_row, column=0, columnspan=2, pady=(15, 5), sticky="ew")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        if not self.show_preview_var.get():
             self.preview_outer_frame.grid_remove()

    def _on_language_select(self, event=None):
        selected = self.selected_language.get()
        new_lang_code = 'en' if selected == 'English' else 'de'
        if new_lang_code != self.current_language:
            logging.info(f"Sprachwechsel angefordert zu: {new_lang_code}")
            self.switch_language(new_lang_code)

    def switch_language(self, lang_code):
        if lang_code not in self.translations:
            logging.warning(f"Ungültiger Sprachcode: {lang_code}")
            return

        self.current_language = lang_code
        lang_texts = self.translations[self.current_language]
        logging.info(f"Wechsle GUI-Sprache zu: {lang_code}")

        try:
            if hasattr(self, 'cam_label'):
                self.cam_label.config(text=lang_texts['camera_label'])
            if hasattr(self, 'camera_combobox'):
                if not self.camera_display_names:
                    self.camera_combobox.config(values=[lang_texts['no_camera_found']])
                else:
                    pass
            if hasattr(self, 'start_button'):
                self.start_button.config(text=lang_texts['start_button'])
            if hasattr(self, 'stop_button'):
                self.stop_button.config(text=lang_texts['stop_button'])
            if hasattr(self, 'exit_button'):
                self.exit_button.config(text=lang_texts['exit_button'])

            if hasattr(self, 'preview_labelframe'):
                self.preview_labelframe.config(text=lang_texts['preview_frame_title'])
            if hasattr(self, 'preview_label') and not hasattr(self.preview_label, 'imgtk'):
                 self.preview_label.config(text=lang_texts['image_error'])

            if hasattr(self, 'status_frame'):
                self.status_frame.config(text=lang_texts['eye_status_frame_title'])
            if hasattr(self, 'left_eye_status_label'):
                self.left_eye_status_label.config(text=lang_texts['left_eye_status_initial'])
            if hasattr(self, 'right_eye_status_label'):
                self.right_eye_status_label.config(text=lang_texts['right_eye_status_initial'])

            if hasattr(self, 'options_frame'):
                self.options_frame.config(text=lang_texts['options_frame_title'])
            if hasattr(self, 'preview_toggle_button'):
                self.preview_toggle_button.config(text=lang_texts['preview_toggle_button'])
            if hasattr(self, 'overlay_checkbutton'):
                self.overlay_checkbutton.config(text=lang_texts['overlay_checkbutton'])
            if hasattr(self, 'language_label'):
                self.language_label.config(text=lang_texts['language_label'])

            if hasattr(self, 'advanced_frame'):
                self.advanced_frame.config(text=lang_texts['advanced_frame_title'])
            if hasattr(self, 'ear_close_label_widget'):
                self.ear_close_label_widget.config(text=lang_texts['ear_close_label'])
            if hasattr(self, 'ear_open_label_widget'):
                self.ear_open_label_widget.config(text=lang_texts['ear_open_label'])
            if hasattr(self, 'cam_width_label_widget'):
                self.cam_width_label_widget.config(text=lang_texts['cam_width_label'])
            if hasattr(self, 'cam_height_label_widget'):
                self.cam_height_label_widget.config(text=lang_texts['cam_height_label'])
            if hasattr(self, 'cam_fps_label_widget'):
                self.cam_fps_label_widget.config(text=lang_texts['cam_fps_label'])
            if hasattr(self, 'process_interval_label_widget'):
                self.process_interval_label_widget.config(text=lang_texts['process_interval_label'])
            if hasattr(self, 'apply_button'):
                self.apply_button.config(text=lang_texts['apply_settings_button'])

            if not self.camera_display_names and hasattr(self, 'camera_combobox'):
                 self.camera_combobox.config(values=[lang_texts['no_camera_found']])
                 self.selected_camera_name.set(lang_texts['no_camera_found'])

            logging.info("GUI-Texte erfolgreich aktualisiert.")

        except Exception as e:
            logging.error(f"Fehler beim Aktualisieren der GUI-Texte für Sprache {lang_code}: {e}", exc_info=True)

    def _toggle_advanced_settings(self):
        if self.advanced_settings_visible.get():
            self.advanced_frame.grid_forget()
            self.advanced_settings_visible.set(False)
            self.advanced_settings_button.config(bootstyle="secondary-outline")
        else:
            self.advanced_frame.grid(row=3, column=0, pady=(0, 10), sticky="ew")
            self.advanced_settings_visible.set(True)
            self.advanced_settings_button.config(bootstyle="secondary")

    def _apply_settings(self):
        logging.info("Versuche, Einstellungen anzuwenden...")
        lang_texts = self.translations[self.current_language]
        settings_error_title = lang_texts.get('settings_error_title', "Fehler bei Einstellungen")
        settings_error_prefix = lang_texts.get('settings_error_prefix', "Einige Eingaben waren ungültig:\n\n")
        settings_applied_title = lang_texts.get('settings_applied_title', "Einstellungen angewendet")
        settings_applied_text = lang_texts.get('settings_applied_text', "Einstellungen wurden übernommen.")
        settings_applied_restart_suffix = lang_texts.get('settings_applied_restart_suffix', "\n...")

        restart_required = False
        error_messages = []

        try:
            new_ear_close = float(self.ear_close_var.get())
            new_ear_open = float(self.ear_open_var.get())
            if not (0 < new_ear_close < new_ear_open < 1.0): error_messages.append("EAR Schwellenwerte ungültig (Bedingung: 0 < CLOSE < OPEN < 1.0)")
            else:
                if abs(new_ear_close - self.applied_ear_close) > 1e-6 or abs(new_ear_open - self.applied_ear_open) > 1e-6:
                     logging.info(f"EAR Thresholds geändert: CLOSE={new_ear_close:.3f}, OPEN={new_ear_open:.3f}")
                     self.applied_ear_close = new_ear_close
                     self.applied_ear_open = new_ear_open
        except ValueError: error_messages.append("EAR Schwellenwerte müssen Zahlen sein (z.B. 0.17).")
        except Exception as e: error_messages.append(f"Fehler bei EAR-Werten: {e}")
        try:
            new_width = int(self.cam_width_var.get())
            if new_width <= 0: error_messages.append("Kamera Breite muss > 0 sein.")
            elif new_width != self.applied_cam_width:
                 logging.info(f"Kamera Breite geändert: {new_width}")
                 self.applied_cam_width = new_width; restart_required = True
        except ValueError: error_messages.append("Kamera Breite muss eine ganze Zahl sein.")
        except Exception as e: error_messages.append(f"Fehler bei Kamera Breite: {e}")
        try:
            new_height = int(self.cam_height_var.get())
            if new_height <= 0: error_messages.append("Kamera Höhe muss > 0 sein.")
            elif new_height != self.applied_cam_height:
                 logging.info(f"Kamera Höhe geändert: {new_height}")
                 self.applied_cam_height = new_height; restart_required = True
        except ValueError: error_messages.append("Kamera Höhe muss eine ganze Zahl sein.")
        except Exception as e: error_messages.append(f"Fehler bei Kamera Höhe: {e}")
        try:
            new_fps = int(self.cam_fps_var.get())
            if new_fps <= 0: error_messages.append("Kamera FPS muss > 0 sein.")
            elif new_fps != self.applied_cam_fps:
                 logging.info(f"Kamera FPS geändert: {new_fps}")
                 self.applied_cam_fps = new_fps; restart_required = True
        except ValueError: error_messages.append("Kamera FPS muss eine ganze Zahl sein.")
        except Exception as e: error_messages.append(f"Fehler bei Kamera FPS: {e}")
        try:
            new_interval = int(self.process_interval_var.get())
            if new_interval <= 0: error_messages.append("Verarbeitungsintervall muss > 0 sein.")
            elif new_interval != self.applied_process_interval:
                 logging.info(f"Verarbeitungsintervall geändert: {new_interval}")
                 self.applied_process_interval = new_interval
        except ValueError: error_messages.append("Verarbeitungsintervall muss eine ganze Zahl sein.")
        except Exception as e: error_messages.append(f"Fehler bei Intervall: {e}")


        if error_messages:
            logging.error("Fehler beim Anwenden der Einstellungen:\n" + "\n".join(error_messages))
            messagebox.showerror(settings_error_title, settings_error_prefix + "\n".join(f"- {msg}" for msg in error_messages))
        else:
            logging.info("Einstellungen erfolgreich validiert und übernommen.")
            full_applied_text = settings_applied_text
            if restart_required:
                full_applied_text += settings_applied_restart_suffix
            messagebox.showinfo(settings_applied_title, full_applied_text)
            if self.advanced_settings_visible.get(): self._toggle_advanced_settings()
            if restart_required:
                if self.tracking_running:
                    logging.warning("Kameraeinstellungen geändert. Tracking wird gestoppt. Bitte neu starten.")
                    self.stop_tracking()
                elif self.preview_running:
                    logging.warning("Kameraeinstellungen geändert. Vorschau wird neu gestartet.")
                    self._start_preview_thread()

    def toggle_preview(self):
        preview_wanted = self.show_preview_var.get()
        logging.info(f"Toggle Preview Display: Gewünschter Zustand = {preview_wanted}")

        if preview_wanted:
            if hasattr(self, 'preview_outer_frame') and not self.preview_outer_frame.winfo_viewable():
                self.preview_outer_frame.grid(row=1, column=0, pady=10, sticky="nsew")
                self.main_container.rowconfigure(1, weight=1)
        else:
            if hasattr(self, 'preview_outer_frame') and self.preview_outer_frame.winfo_viewable():
                self.preview_outer_frame.grid_remove()
                self.main_container.rowconfigure(1, weight=0)

        if not self.tracking_running:
            if preview_wanted:
                if not self.preview_running:
                    self._start_preview_thread()
            else:
                if self.preview_running:
                    self._stop_preview_thread()
        else:
            if not preview_wanted:
                logging.info("Vorschau während Tracking deaktiviert. Leere Queue.")
                while not self.frame_queue.empty():
                    try: self.frame_queue.get_nowait()
                    except queue.Empty: break
            else:
                logging.info("Vorschau während Tracking aktiviert.")

    def update_preview_from_queue(self):
        if self.is_closing: return
        frame = None
        try: frame = self.frame_queue.get_nowait()
        except queue.Empty: pass
        except Exception as e: logging.error(f"Fehler Queue lesen: {e}")

        if frame is not None and self.show_preview_var.get():
            if hasattr(self, 'preview_outer_frame') and not self.preview_outer_frame.winfo_viewable():
                 self.preview_outer_frame.grid(row=1, column=0, pady=10, sticky="nsew")
                 self.main_container.rowconfigure(1, weight=1)
            self._display_frame(frame)

        self.root.after(PREVIEW_UPDATE_DELAY_MS, self.update_preview_from_queue)


    def _enqueue_frame(self, frame):
        if frame is None or self.is_closing: return
        if self.tracking_running or self.show_preview_var.get():
             try:
                 while not self.frame_queue.empty(): self.frame_queue.get_nowait()
                 self.frame_queue.put_nowait(frame)
             except queue.Full: pass
             except Exception as e: logging.warning(f"Fehler Enqueue: {e}")
        else:
             while not self.frame_queue.empty():
                 try: self.frame_queue.get_nowait()
                 except queue.Empty: break

    def _display_frame(self, frame):
        if frame is None or self.is_closing or not self.show_preview_var.get(): return
        if not hasattr(self, 'preview_label') or not self.preview_label.winfo_exists(): return
        if not hasattr(self, 'preview_outer_frame') or not self.preview_outer_frame.winfo_viewable(): return

        try:
            h_in, w_in = frame.shape[:2]
            if h_in <= 0 or w_in <= 0: return

            target_w = self.preview_labelframe.winfo_width() - 10
            target_h = self.preview_labelframe.winfo_height() - 30
            if target_w <= 1 or target_h <= 1:
                target_w = self.preview_outer_frame.winfo_width() - 10
                target_h = self.preview_outer_frame.winfo_height() - 30
            if target_w <= 1 or target_h <= 1: return

            scale = min(target_w / w_in, target_h / h_in)
            scale = min(scale, 1.0)
            new_w, new_h = int(w_in * scale), int(h_in * scale)
            if new_w <=0 or new_h <= 0: return

            resized_frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            cv2image = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(cv2image)
            imgtk = ImageTk.PhotoImage(image=img)

            self.preview_label.imgtk = imgtk
            self.preview_label.config(image=imgtk, text="")

        except Exception as e:
            if not self.is_closing:
                logging.error(f"Fehler _display_frame: {e}", exc_info=False)
                try:
                    self.preview_label.config(image='', text=self.translations[self.current_language].get('image_error', 'Image Error'))
                    self.preview_label.imgtk = None
                except: pass

    def _release_camera(self, cap_type):
        with self.camera_lock:
            cap, cap_name_internal = (self.preview_cap, "Vorschau") if cap_type == "preview" else (self.tracking_cap, "Tracking")
            if cap and cap.isOpened():
                cam_display_name = ""
                try:
                    cam_display_name = self.selected_camera_name.get()
                    if not cam_display_name or cam_display_name == self.translations[self.current_language].get('no_camera_found', "Keine Kamera"):
                         idx = self.selected_camera_index.get()
                         for name, index in self.camera_name_to_index.items():
                              if index == idx: cam_display_name = name; break
                         if not cam_display_name: cam_display_name = f"({cap_name_internal}-Kamera Index {idx})"
                except Exception:
                    cam_display_name = f"({cap_name_internal}-Kamera)"

                logging.info(f"Gebe {cap_name_internal}-Kamera frei ('{cam_display_name}')...");
                try: cap.release()
                except Exception as e: logging.error(f"Fehler Freigabe {cap_name_internal} ('{cam_display_name}'): {e}")
                finally:
                    if cap_type == "preview": self.preview_cap = None
                    else: self.tracking_cap = None
                    logging.info(f"{cap_name_internal}-Kamera ('{cam_display_name}') freigegeben.")

    def _stop_preview_thread(self):
        if self.preview_running:
            logging.info("Stoppe Vorschau-Thread..."); self.preview_running = False
            thread = self.preview_thread; self.preview_thread = None
            if thread is not None:
                thread.join(timeout=3.5);
                if thread and thread.is_alive(): logging.warning("Vorschau-Thread nicht beendet.")
                else: logging.info("Vorschau-Thread beendet.")
            else:
                 logging.info("Kein Vorschau-Thread zum Stoppen gefunden.")

            self._release_camera("preview");
            if not self.tracking_running:
                 while not self.frame_queue.empty():
                     try: self.frame_queue.get_nowait()
                     except queue.Empty: break
            logging.info("Vorschau Stop abgeschlossen.")

            if not self.is_closing and hasattr(self, 'preview_label') and self.placeholder_photo:
                 try:
                     self.preview_label.config(image=self.placeholder_photo)
                     self.preview_label.imgtk = None
                 except tk.TclError: pass

    def _start_preview_thread(self):
        if self.tracking_running or self.is_closing or not self.show_preview_var.get():
            if self.tracking_running: logging.debug("Vorschau nicht gestartet (Tracking läuft).")
            if self.is_closing: logging.debug("Vorschau nicht gestartet (App schließt).")
            if not self.show_preview_var.get(): logging.debug("Vorschau nicht gestartet (explizit deaktiviert).")
            return

        self._stop_preview_thread();

        cam_idx = self.selected_camera_index.get()
        cam_name = self.selected_camera_name.get()
        if cam_idx == -1:
            warn_title = self.translations[self.current_language].get('no_camera_warning_title', "Keine Kamera")
            warn_text = self.translations[self.current_language].get('no_camera_warning_text', "Bitte Kamera wählen.")
            logging.warning("Keine Kamera für Vorschau ausgewählt."); messagebox.showwarning(warn_title, warn_text)
            return

        if hasattr(self, 'preview_outer_frame') and not self.preview_outer_frame.winfo_viewable():
             self.preview_outer_frame.grid(row=1, column=0, pady=10, sticky="nsew")
             self.main_container.rowconfigure(1, weight=1)

        logging.info(f"Starte Vorschau für '{cam_name}' (Index {cam_idx})..."); self.preview_running = True
        name = f"PreviewThread-{cam_idx}"; self.preview_thread = threading.Thread(target=self._preview_worker, args=(cam_idx, cam_name), name=name, daemon=True)
        self.preview_thread.start()

    def _preview_worker(self, camera_index, camera_name):
        logging.info(f"Vorschau-Worker für '{camera_name}' gestartet.")
        cap = None
        try:
            with self.camera_lock:
                logging.info(f"Öffne Vorschau-Kamera '{camera_name}'...");
                cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW if platform.system() == "Windows" else None)
                if not cap or not cap.isOpened():
                    logging.warning(f"Fallback: Versuche Kamera {camera_index} ohne DSHOW...")
                    cap = cv2.VideoCapture(camera_index)

                if cap and cap.isOpened():
                     cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.applied_cam_width)
                     cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.applied_cam_height)
                     cap.set(cv2.CAP_PROP_FPS, self.applied_cam_fps)
                     actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                     actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                     actual_fps = cap.get(cv2.CAP_PROP_FPS)
                     if actual_fps <= 0: actual_fps = self.applied_cam_fps
                     logging.info(f"Vorschau-Kamera '{camera_name}' offen. Angefordert: {self.applied_cam_width}x{self.applied_cam_height} @{self.applied_cam_fps}FPS. Tatsächlich: {actual_w}x{actual_h} @{actual_fps:.2f}FPS")
                     self.preview_cap = cap
                else:
                    logging.error(f"Fehler Öffnen Vorschau '{camera_name}'."); self.preview_running = False;
                    err_title = self.translations[self.current_language].get('camera_error_title', "Kamerafehler")
                    err_text_tmpl = self.translations[self.current_language].get('camera_error_text_template', "Kamera '{}' konnte nicht geöffnet werden.")
                    if not self.is_closing: self.root.after(0, lambda cn=camera_name: messagebox.showerror(err_title, err_text_tmpl.format(cn)))
                    if not self.is_closing and hasattr(self, 'preview_outer_frame'):
                         self.root.after(0, lambda: self.preview_outer_frame.grid_remove())
                         self.root.after(0, lambda: self.main_container.rowconfigure(1, weight=0))
                    return

            last_t = time.monotonic()
            error_logged = False
            while self.preview_running:
                curr_t = time.monotonic();
                if curr_t - last_t < 0.015: time.sleep(0.005); continue
                last_t = curr_t

                frame = None
                success = False
                with self.camera_lock:
                    if not self.preview_cap or not self.preview_cap.isOpened():
                        if self.preview_running:
                             logging.warning(f"Vorschau-Kamera '{camera_name}' ist unerwartet geschlossen.")
                        break
                    success, frame = self.preview_cap.read()

                if success and frame is not None and frame.size > 0:
                    frame_to_show = cv2.flip(frame, 1)
                    if self.show_preview_var.get():
                        self._enqueue_frame(frame_to_show)
                    error_logged = False
                elif not success:
                    if not error_logged: logging.warning(f"Lesefehler Vorschau '{camera_name}'."); error_logged = True
                    time.sleep(0.1)
                elif frame is None or frame.size == 0:
                     if not error_logged: logging.warning(f"Leeren/ungültigen Frame von Vorschau '{camera_name}' empfangen."); error_logged = True
                     time.sleep(0.1)

        except Exception as e:
            if self.preview_running:
                logging.error(f"Fehler in Preview-Loop '{camera_name}': {e}", exc_info=True)
        finally:
            logging.info(f"Vorschau-Worker '{camera_name}' beendet.");
            if self.preview_cap:
                self._release_camera("preview")
            self.preview_running = False

    def on_camera_select(self, event=None):
        name = self.selected_camera_name.get()
        idx = self.camera_name_to_index.get(name, -1)
        no_cam_text = self.translations[self.current_language].get('no_camera_found', "Keine Kamera")
        if name == no_cam_text:
            idx = -1

        if idx != -1 and idx != self.selected_camera_index.get():
            self.selected_camera_index.set(idx)
            logging.info(f"Kamera '{name}' (Index {idx}) ausgewählt.")
            if not self.tracking_running:
                if self.show_preview_var.get():
                    self._start_preview_thread()
        elif idx == -1 and name != no_cam_text:
             logging.warning(f"Ungültiger Kameraname ausgewählt: {name}")
        elif idx != -1 and idx == self.selected_camera_index.get():
             logging.debug(f"Kamera '{name}' war bereits ausgewählt.")
        elif idx == -1 and name == no_cam_text:
             logging.info("Auswahl 'Keine Kamera'. Stoppe Vorschau.")
             self.selected_camera_index.set(-1)
             if not self.tracking_running:
                 self._stop_preview_thread()
                 if hasattr(self, 'preview_outer_frame'):
                     self.preview_outer_frame.grid_remove()
                     self.main_container.rowconfigure(1, weight=0)


    def start_tracking(self):
        if self.is_closing or self.tracking_running: return
        logging.info("Start Tracking Klick."); idx = self.selected_camera_index.get()
        name = self.selected_camera_name.get()
        warn_title = self.translations[self.current_language].get('no_camera_warning_title', "Keine Kamera")
        warn_text = self.translations[self.current_language].get('no_camera_warning_text', "Bitte Kamera wählen.")
        if idx == -1: messagebox.showwarning(warn_title, warn_text); return

        logging.info(f"Starte Tracking für '{name}' (Index {idx})...");
        self._stop_preview_thread();

        if self.show_preview_var.get():
            if hasattr(self, 'preview_outer_frame') and not self.preview_outer_frame.winfo_viewable():
                self.preview_outer_frame.grid(row=1, column=0, pady=10, sticky="nsew")
                self.main_container.rowconfigure(1, weight=1)
        else:
            if hasattr(self, 'preview_outer_frame') and self.preview_outer_frame.winfo_viewable():
                self.preview_outer_frame.grid_remove()
                self.main_container.rowconfigure(1, weight=0)

        logging.info("Warte auf Kamera..."); time.sleep(0.5)
        self.left_eye_closed_state = False; self.right_eye_closed_state = False
        self.x_key_down = False; self.c_key_down = False
        self.both_were_closed = False; self.face_detected_status = False
        logging.info("Augen- und Tasten-Status Reset.")

        self.tracking_running = True
        self.start_button.config(state=DISABLED); self.stop_button.config(state=NORMAL)
        self.exit_button.config(state=DISABLED); self.camera_combobox.config(state=DISABLED)
        self.overlay_checkbutton.config(state=NORMAL)
        self.preview_toggle_button.config(state=NORMAL)
        self.advanced_settings_button.config(state=DISABLED)
        self.language_combobox.config(state=DISABLED)

        self.root.after(0, self.update_eye_status_display)
        thread_name = f"TrackingThread-{idx}"; self.tracking_thread = threading.Thread(target=self.eye_tracker_loop, args=(idx, name), name=thread_name, daemon=True)
        self.tracking_thread.start()

    def stop_tracking(self):
        if self.is_closing or not self.tracking_running: return
        logging.info("Stop Tracking Klick."); self.tracking_running = False

        thread = self.tracking_thread; self.tracking_thread = None
        if thread is not None:
            logging.info("Warte auf Tracking-Thread...");
            thread.join(timeout=3.5);
            if thread.is_alive(): logging.warning("Tracking-Thread nicht beendet.")
            else: logging.info("Tracking-Thread beendet.")
        else:
            logging.info("Kein Tracking-Thread zum Stoppen gefunden.")

        self._release_camera("tracking")

        while not self.frame_queue.empty():
             try: self.frame_queue.get_nowait()
             except queue.Empty: break

        if self.x_key_down:
            try: pydirectinput.keyUp('x'); logging.info("Stop: Gehaltenes 'x' losgelassen.")
            except Exception as e: logging.warning(f"Fehler keyUp('x') beim Stoppen: {e}")
            self.x_key_down = False
        if self.c_key_down:
            try: pydirectinput.keyUp('c'); logging.info("Stop: Gehaltenes 'c' losgelassen.")
            except Exception as e: logging.warning(f"Fehler keyUp('c') beim Stoppen: {e}")
            self.c_key_down = False

        self.left_eye_closed_state = False; self.right_eye_closed_state = False;
        self.left_ear_value = 0.0; self.right_ear_value = 0.0; self.face_detected_status = False;
        self.both_were_closed = False
        logging.info("Tracking-Status Reset.")

        if not self.is_closing: self.root.after(0, self.update_gui_after_stop)
        logging.info("Tracking Stop abgeschlossen.")

    def update_gui_after_stop(self):
        if self.is_closing: return
        logging.info("Update GUI nach Stop..."); available = bool(self.camera_display_names)
        no_cam_text = self.translations[self.current_language].get('no_camera_found', "Keine Kamera")

        self.start_button.config(state=NORMAL if available else DISABLED)
        self.stop_button.config(state=DISABLED)
        self.exit_button.config(state=NORMAL)
        self.camera_combobox.config(state="readonly" if available else DISABLED)
        if not available:
             self.camera_combobox.set(no_cam_text)
             self.selected_camera_name.set(no_cam_text)
        self.overlay_checkbutton.config(state=DISABLED)
        self.preview_toggle_button.config(state=NORMAL if available else DISABLED)
        self.advanced_settings_button.config(state=NORMAL if available else DISABLED)
        self.language_combobox.config(state="readonly")

        if available and self.selected_camera_index.get() != -1 and self.show_preview_var.get():
             logging.info("Starte Vorschau neu nach Stop.");
             self._start_preview_thread()
             if hasattr(self, 'preview_outer_frame') and not self.preview_outer_frame.winfo_viewable():
                  self.preview_outer_frame.grid(row=1, column=0, pady=10, sticky="nsew")
                  self.main_container.rowconfigure(1, weight=1)
        elif hasattr(self, 'preview_outer_frame') and self.preview_outer_frame.winfo_viewable():
             self.preview_outer_frame.grid_remove()
             self.main_container.rowconfigure(1, weight=0)
             logging.info("Vorschau nach Stop ausgeblendet.")
             if hasattr(self, 'preview_label') and self.placeholder_photo:
                 try:
                     self.preview_label.config(image=self.placeholder_photo)
                     self.preview_label.imgtk = None
                 except tk.TclError: pass

        self.root.after(0, self.update_eye_status_display);
        logging.info("GUI Update nach Stop fertig.")

    def update_eye_status_display(self):
        if not self.root or not self.root.winfo_exists() or self.is_closing: return

        left_text, right_text = "Links: ---", "Rechts: ---"
        left_style, right_style = DEFAULT, DEFAULT

        if self.tracking_running:
             if not self.face_detected_status:
                 left_text, right_text = "Links: Suche Gesicht...", "Rechts: Suche Gesicht..."
                 left_style, right_style = SECONDARY, SECONDARY
             else:
                 lc = self.left_eye_closed_state
                 rc = self.right_eye_closed_state
                 left_ear_display = f"(EAR: {self.left_ear_value:.3f})" if not lc else ""
                 right_ear_display = f"(EAR: {self.right_ear_value:.3f})" if not rc else ""
                 left_text = f"Links: {'GESCHLOSSEN' if lc else 'OFFEN'} {left_ear_display}".strip()
                 left_style = DANGER if lc else SUCCESS
                 right_text = f"Rechts: {'GESCHLOSSEN' if rc else 'OFFEN'} {right_ear_display}".strip()
                 right_style = DANGER if rc else SUCCESS

        elif not self.tracking_running:
             lang_texts = self.translations[self.current_language]
             left_text = lang_texts['left_eye_status_initial']
             right_text = lang_texts['right_eye_status_initial']

        try:
            if hasattr(self, 'left_eye_status_label') and self.left_eye_status_label.winfo_exists():
                self.left_eye_status_label.config(text=left_text, bootstyle=left_style)
            if hasattr(self, 'right_eye_status_label') and self.right_eye_status_label.winfo_exists():
                self.right_eye_status_label.config(text=right_text, bootstyle=right_style)
        except Exception as e:
             if not self.is_closing: logging.error(f"Fehler Status Update: {e}", exc_info=True)


    def eye_tracker_loop(self, camera_index, camera_name):
        logging.info(f"Tracking-Worker für '{camera_name}' gestartet.")
        global face_mesh
        if face_mesh is None:
            logging.error("FaceMesh ist None im Tracking-Worker!")
            if not self.is_closing: self.root.after(0, self.stop_tracking)
            return

        cap = None; frame_count = 0
        error_logged = False
        face_mesh_initialized = False

        try:
            with self.camera_lock:
                logging.info(f"Öffne Tracking-Kamera '{camera_name}'...");
                cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW if platform.system() == "Windows" else None)
                if not cap or not cap.isOpened():
                    logging.warning(f"Fallback: Versuche Tracking-Kamera {camera_index} ohne DSHOW...")
                    cap = cv2.VideoCapture(camera_index)

                if cap and cap.isOpened():
                     cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.applied_cam_width)
                     cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.applied_cam_height)
                     cap.set(cv2.CAP_PROP_FPS, self.applied_cam_fps)
                     actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                     actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                     actual_fps = cap.get(cv2.CAP_PROP_FPS)
                     if actual_fps <= 0: actual_fps = self.applied_cam_fps
                     logging.info(f"Tracking-Kamera '{camera_name}' offen. Angefordert: {self.applied_cam_width}x{self.applied_cam_height} @{self.applied_cam_fps}FPS. Tatsächlich: {actual_w}x{actual_h} @{actual_fps:.2f}FPS")
                     self.tracking_cap = cap
                else:
                    logging.error(f"FEHLER Öffnen Tracking '{camera_name}'!")
                    err_title = self.translations[self.current_language].get('camera_error_title', "Kamerafehler")
                    err_text_tmpl = self.translations[self.current_language].get('camera_error_text_template', "Kamera '{}' konnte nicht geöffnet werden.")
                    if not self.is_closing:
                         self.root.after(0, lambda cn=camera_name: messagebox.showerror(err_title, err_text_tmpl.format(cn)))
                         self.root.after(0, self.stop_tracking)
                    return

            logging.info("Starte Tracking Loop...");
            last_process_time = time.monotonic()
            frame_skip_counter = 0

            while self.tracking_running:
                frame_original = None; current_time = time.monotonic()

                try:
                     success = False; frame_original = None
                     with self.camera_lock:
                         if not self.tracking_cap or not self.tracking_cap.isOpened():
                             if self.tracking_running:
                                logging.warning(f"Tracking-Kamera '{camera_name}' wurde unerwartet geschlossen.")
                             break
                         success, frame_original = self.tracking_cap.read()

                     if not success or frame_original is None or frame_original.size == 0:
                         if not error_logged:
                             logging.warning(f"Lesefehler oder leerer Frame beim Tracking '{camera_name}'. Warte kurz."); error_logged = True
                         time.sleep(0.1); continue
                     error_logged = False

                     last_process_time = current_time;
                     frame_original = cv2.flip(frame_original, 1)
                     frame_to_show = frame_original.copy()

                     frame_skip_counter += 1
                     if frame_skip_counter >= self.applied_process_interval:
                         frame_skip_counter = 0

                         rgb_frame = cv2.cvtColor(frame_original, cv2.COLOR_BGR2RGB)
                         rgb_frame.flags.writeable = False
                         results = face_mesh.process(rgb_frame)
                         rgb_frame.flags.writeable = True

                         current_face_detected = bool(results.multi_face_landmarks)
                         needs_gui_status_update = False

                         if self.face_detected_status != current_face_detected:
                             self.face_detected_status = current_face_detected
                             needs_gui_status_update = True
                             if not current_face_detected:
                                  logging.info("Gesicht verloren.")
                                  if self.x_key_down:
                                      try: pydirectinput.keyUp('x')
                                      except Exception as e: logging.error(f"Fehler keyUp('x') bei Gesichtsverlust: {e}")
                                      self.x_key_down = False
                                  if self.c_key_down:
                                      try: pydirectinput.keyUp('c')
                                      except Exception as e: logging.error(f"Fehler keyUp('c') bei Gesichtsverlust: {e}")
                                      self.c_key_down = False
                                  self.left_eye_closed_state = False; self.right_eye_closed_state = False
                                  self.both_were_closed = False
                                  self.left_ear_value, self.right_ear_value = 0.0, 0.0
                             else:
                                  logging.info("Gesicht gefunden.")
                                  self.left_eye_closed_state = False; self.right_eye_closed_state = False
                                  self.both_were_closed = False
                                  self.x_key_down = False; self.c_key_down = False

                         if current_face_detected:
                             face_landmarks = results.multi_face_landmarks[0]
                             landmarks = face_landmarks.landmark
                             h, w = frame_original.shape[:2]

                             if self.show_overlay_var.get():
                                  try:
                                      mp_drawing.draw_landmarks(image=frame_to_show, landmark_list=face_landmarks, connections=mp_face_mesh.FACEMESH_TESSELATION, landmark_drawing_spec=None, connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style())
                                      mp_drawing.draw_landmarks(image=frame_to_show, landmark_list=face_landmarks, connections=mp_face_mesh.FACEMESH_CONTOURS, landmark_drawing_spec=None, connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_contours_style())
                                      mp_drawing.draw_landmarks(image=frame_to_show, landmark_list=face_landmarks, connections=mp_face_mesh.FACEMESH_IRISES, landmark_drawing_spec=None, connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_iris_connections_style())
                                  except AttributeError:
                                      logging.warning("Konnte Overlay nicht zeichnen (mp_drawing Fehler).")
                                  except Exception as e:
                                      logging.error(f"Unbekannter Fehler beim Overlay zeichnen: {e}")

                             try:
                                 left_lm_pixels = np.array([(landmarks[idx].x * w, landmarks[idx].y * h) for idx in LEFT_EAR_IDX], dtype=np.float32)
                                 right_lm_pixels = np.array([(landmarks[idx].x * w, landmarks[idx].y * h) for idx in RIGHT_EAR_IDX], dtype=np.float32)

                                 self.left_ear_value = calculate_ear(left_lm_pixels) if len(left_lm_pixels) == 6 else 0.0
                                 self.right_ear_value = calculate_ear(right_lm_pixels) if len(right_lm_pixels) == 6 else 0.0

                                 left_state_changed = False
                                 is_left_now = self.left_eye_closed_state
                                 if self.left_eye_closed_state:
                                     if self.left_ear_value > self.applied_ear_open:
                                         is_left_now = False; left_state_changed = True
                                 else:
                                     if self.left_ear_value < self.applied_ear_close:
                                         is_left_now = True; left_state_changed = True

                                 right_state_changed = False
                                 is_right_now = self.right_eye_closed_state
                                 if self.right_eye_closed_state:
                                     if self.right_ear_value > self.applied_ear_open:
                                         is_right_now = False; right_state_changed = True
                                 else:
                                     if self.right_ear_value < self.applied_ear_close:
                                         is_right_now = True; right_state_changed = True

                                 if left_state_changed or right_state_changed:
                                     needs_gui_status_update = True

                                 both_closed_now = is_left_now and is_right_now

                                 if both_closed_now != self.both_were_closed:
                                     needs_gui_status_update = True
                                     try:
                                         if self.x_key_down: pydirectinput.keyUp('x'); self.x_key_down = False; logging.debug("Beide Augen Wechsel: Löse 'x'.")
                                         if self.c_key_down: pydirectinput.keyUp('c'); self.c_key_down = False; logging.debug("Beide Augen Wechsel: Löse 'c'.")

                                         if both_closed_now:
                                             logging.info("BEIDE AUGEN GESCHLOSSEN -> Drücke X & C")
                                             pydirectinput.keyDown('x'); pydirectinput.keyDown('c')
                                             time.sleep(0.05)
                                             pydirectinput.keyUp('x'); pydirectinput.keyUp('c')
                                         else:
                                             logging.info("BEIDE AUGEN GEÖFFNET (von geschlossen) -> Drücke X")
                                             pydirectinput.press('x')

                                     except Exception as e: logging.error(f"Fehler pydirectinput bei 'beide Augen' Wechsel: {e}")
                                     self.both_were_closed = both_closed_now

                                 elif is_left_now and not is_right_now:
                                     if not self.x_key_down:
                                         if self.c_key_down:
                                             try: pydirectinput.keyUp('c'); self.c_key_down = False; logging.debug("Wechsel zu Links: Löse 'c'.")
                                             except Exception as e: logging.error(f"Fehler keyUp('c') beim Wechsel zu links: {e}")
                                         try:
                                             logging.info("NUR LINKS GESCHLOSSEN -> Halte X")
                                             pydirectinput.keyDown('x'); self.x_key_down = True; needs_gui_status_update = True
                                         except Exception as e: logging.error(f"Fehler pydirectinput.keyDown('x'): {e}")

                                 elif is_right_now and not is_left_now:
                                     if not self.c_key_down:
                                         if self.x_key_down:
                                             try: pydirectinput.keyUp('x'); self.x_key_down = False; logging.debug("Wechsel zu Rechts: Löse 'x'.")
                                             except Exception as e: logging.error(f"Fehler keyUp('x') beim Wechsel zu rechts: {e}")
                                         try:
                                             logging.info("NUR RECHTS GESCHLOSSEN -> Halte C")
                                             pydirectinput.keyDown('c'); self.c_key_down = True; needs_gui_status_update = True
                                         except Exception as e: logging.error(f"Fehler pydirectinput.keyDown('c'): {e}")

                                 elif not is_left_now and not is_right_now:
                                     released_key = False
                                     if self.x_key_down:
                                         try: pydirectinput.keyUp('x'); self.x_key_down = False; released_key = True; logging.info("Beide Augen offen: Löse 'x'.")
                                         except Exception as e: logging.error(f"Fehler pydirectinput.keyUp('x'): {e}")
                                     if self.c_key_down:
                                         try: pydirectinput.keyUp('c'); self.c_key_down = False; released_key = True; logging.info("Beide Augen offen: Löse 'c'.")
                                         except Exception as e: logging.error(f"Fehler pydirectinput.keyUp('c'): {e}")
                                     if released_key: needs_gui_status_update = True

                                 self.left_eye_closed_state = is_left_now
                                 self.right_eye_closed_state = is_right_now

                             except Exception as e:
                                logging.error(f"Fehler bei EAR/Keypress Verarbeitung: {e}", exc_info=True);
                                if self.x_key_down:
                                    try: pydirectinput.keyUp('x'); self.x_key_down = False
                                    except: pass
                                if self.c_key_down:
                                    try: pydirectinput.keyUp('c'); self.c_key_down = False
                                    except: pass
                                needs_gui_status_update = True

                         if self.show_preview_var.get() or self.show_overlay_var.get():
                              self._enqueue_frame(frame_to_show)

                         if needs_gui_status_update and self.tracking_running:
                             self.root.after(0, self.update_eye_status_display)

                     elif self.show_preview_var.get() and not self.show_overlay_var.get():
                          self._enqueue_frame(frame_to_show)

                except Exception as e:
                    if self.tracking_running: logging.error(f"Schwerer Fehler in Tracking-Loop-Body: {e}", exc_info=True)
                    if self.x_key_down:
                         try: pydirectinput.keyUp('x'); self.x_key_down = False
                         except: pass
                    if self.c_key_down:
                         try: pydirectinput.keyUp('c'); self.c_key_down = False
                         except: pass
                    time.sleep(0.5)
        finally:
            logging.info(f"Tracking-Worker '{camera_name}' wird beendet...");
            if self.x_key_down:
                try: pydirectinput.keyUp('x'); logging.info("Worker Ende: Löse 'x'.")
                except Exception as e: logging.warning(f"Fehler keyUp('x') am Worker Ende: {e}")
            if self.c_key_down:
                try: pydirectinput.keyUp('c'); logging.info("Worker Ende: Löse 'c'.")
                except Exception as e: logging.warning(f"Fehler keyUp('c') am Worker Ende: {e}")

            self._release_camera("tracking")
            logging.info(f"Tracking-Worker '{camera_name}' sauber beendet.")

    def on_close(self):
        if self.is_closing: return
        self.is_closing = True; logging.info("Schließsequenz gestartet...")

        try:
             if hasattr(self, 'start_button') and self.start_button.winfo_exists(): self.start_button.config(state=DISABLED)
             if hasattr(self, 'stop_button') and self.stop_button.winfo_exists(): self.stop_button.config(state=DISABLED)
             if hasattr(self, 'exit_button') and self.exit_button.winfo_exists(): self.exit_button.config(state=DISABLED)
             if hasattr(self, 'camera_combobox') and self.camera_combobox.winfo_exists(): self.camera_combobox.config(state=DISABLED)
             if hasattr(self, 'overlay_checkbutton') and self.overlay_checkbutton.winfo_exists(): self.overlay_checkbutton.config(state=DISABLED)
             if hasattr(self, 'preview_toggle_button') and self.preview_toggle_button.winfo_exists(): self.preview_toggle_button.config(state=DISABLED)
             if hasattr(self, 'advanced_settings_button') and self.advanced_settings_button.winfo_exists(): self.advanced_settings_button.config(state=DISABLED)
             if hasattr(self, 'language_combobox') and self.language_combobox.winfo_exists(): self.language_combobox.config(state=DISABLED)
        except tk.TclError: pass
        except Exception as e: logging.warning(f"Fehler beim Deaktivieren der GUI beim Schließen: {e}")

        self.tracking_running = False; self.preview_running = False;
        time.sleep(0.1)

        tracking_thread_local = self.tracking_thread
        if tracking_thread_local and tracking_thread_local.is_alive():
            logging.info("Warte auf Tracking-Thread (on_close)...")
            tracking_thread_local.join(timeout=5.0)
            if tracking_thread_local.is_alive(): logging.warning("Tracking-Thread nach on_close nicht beendet.")
            else: logging.info("Tracking-Thread (on_close) beendet.")

        if self.x_key_down:
            try: pydirectinput.keyUp('x'); logging.info("On Close: Löse evtl. hängendes 'x'.")
            except Exception as e: logging.warning(f"On Close: Fehler keyUp('x'): {e}")
        if self.c_key_down:
            try: pydirectinput.keyUp('c'); logging.info("On Close: Löse evtl. hängendes 'c'.")
            except Exception as e: logging.warning(f"On Close: Fehler keyUp('c'): {e}")

        self._stop_preview_thread()

        global face_mesh
        if face_mesh:
            try:
                logging.info("Schließe Mediapipe FaceMesh...")
                face_mesh.close();
                logging.info("Mediapipe geschlossen.")
            except Exception as e: logging.warning(f"Fehler beim Schließen von Mediapipe: {e}")
            finally: face_mesh = None

        logging.info("Zerstöre Hauptfenster...")
        if self.root and self.root.winfo_exists():
            try: self.root.destroy()
            except tk.TclError: logging.info("Hauptfenster bereits zerstört.")
        logging.info("--- Eye Tracker Application Closed ---")


if __name__ == "__main__":
    if platform.system() == "Windows":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
            logging.info("DPI Awareness für Windows gesetzt.")
        except Exception as e:
            logging.warning(f"Konnte DPI Awareness nicht setzen: {e}")

    logging.info("Starte Applikations-Hauptblock.")

    try:
        logging.info("Initialisiere Mediapipe FaceMesh (CPU)...")
        face_mesh = mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5)
        logging.info("Mediapipe FaceMesh initialisiert.")

    except Exception as e:
        logging.error(f"Fehler Initialisierung Mediapipe: {e}", exc_info=True)
        try:
            root_temp = tk.Tk(); root_temp.withdraw()
            messagebox.showerror("Initialisierungsfehler", f"Mediapipe konnte nicht initialisiert werden:\n{e}\n\nDie Anwendung wird beendet.")
            root_temp.destroy()
        except Exception as e2:
            print(f"FEHLER: Mediapipe konnte nicht initialisiert werden: {e}")
            print(f"FEHLER: Konnte keine Fehler-MessageBox anzeigen: {e2}")
        face_mesh = None; exit(1)

    theme_name = 'darkly'
    logging.info(f"Verwende ttkbootstrap Theme: '{theme_name}'")
    try:
        root = ttkb.Window(themename=theme_name)
    except Exception as e:
        logging.error(f"Fehler beim Laden von ttkbootstrap Theme '{theme_name}': {e}. Fallback auf Standard Tk.")
        root = tk.Tk()

    app = EyeTrackerApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt empfangen. Beende Anwendung...")
        app.on_close()
    logging.info("Applikations-Hauptschleife beendet.")