# LockdownEyeProtocol v1.1.1

**Autor:** tcbob1994

Ein Eyetracker, der deine Webcam nutzt, um Blinzeln zu erkennen und Tastatureingaben zu simulieren. Gedacht zur Steuerung von Anwendungen oder Spielen durch Blinzeln (z.B. für Barrierefreiheit oder spezielle Interaktionen).

Das Programm basiert auf Python, Mediapipe zur Gesichtserkennung, OpenCV zur Kamera-Interaktion und ttkbootstrap für eine moderne grafische Benutzeroberfläche.

## Wichtiger Hinweis

Bitte beachte: Dieses Programm wurde als Test und Proof-of-Concept von mir entwickelt. Es demonstriert, dass die grundlegende Augenerkennung und Tastensimulation funktioniert, ist aber **nicht** als eine 100% zuverlässige oder fehlerfreie Anwendung gedacht.

Du wirst möglicherweise auf Ungenauigkeiten bei der Erkennung, Performance-Probleme oder andere Bugs stoßen, besonders unter variierenden Lichtbedingungen oder mit unterschiedlichen Webcams. Betrachte es als Lernprojekt oder Demonstration der Möglichkeiten!

Mir war Langweilig.

## Ausführbare Datei (.exe) – Einfacher Start (Experimentell)

Wenn du dir die Installation von Python und den ganzen Bibliotheken sparen möchtest, habe ich eine ausführbare Windows-Datei (`.exe`) erstellt. Diese kannst du normalerweise direkt starten, ohne etwas installieren zu müssen (außer eventuell benötigten System-Runtimes, falls sie fehlen).

**Download-Link:**
[`LockdownEyetracker.exe` herunterladen](https://github.com/tcbob1994/LockdownEyetracker/releases/tag/release)

**🚨 Wichtige Sicherheitswarnung:**
Das Ausführen von `.exe`-Dateien, die du aus unbekannten Quellen im Internet herunterlädst, ist **grundsätzlich ein Sicherheitsrisiko**. Virenscanner schlagen bei selbst erstellten `.exe`-Dateien manchmal fälschlicherweise Alarm (False Positives).

Lade diese Datei nur herunter und führe sie aus, wenn du **mir vertraust** und dir der potenziellen Risiken bewusst bist. Die Nutzung der `.exe`-Datei erfolgt vollständig **auf deine eigene Gefahr**. Ich übernehme keine Haftung für eventuell entstehende Probleme oder Schäden auf deinem System.

**Hinweis:** Da dies, wie oben erwähnt, ein Testprojekt ist, kann auch die `.exe`-Datei noch Fehler enthalten oder nicht auf jedem System perfekt laufen. Im Zweifelsfall ist es immer sicherer und transparenter, den Python-Code selbst auszuführen (siehe [Installation](#installation)).

## Features

*   Echtzeit-Augenerkennung (links, rechts, beide) über deine Webcam.
*   Simuliert Tastendrücke basierend auf dem Blinzelstatus.
*   Grafische Benutzeroberfläche (GUI) mit:
    *   Automatischer Kameraerkennung und Auswahlmöglichkeit.
    *   Start/Stop-Steuerung für das Tracking.
    *   Live-Vorschaufenster der Kamera (an-/abschaltbar).
    *   Optionales Overlay mit erkanntem Gesichtsnetz (an-/abschaltbar).
    *   Live-Statusanzeige für jedes Auge (Offen/Geschlossen) und den EAR-Wert (Eye Aspect Ratio).
    *   Sprachumschaltung der Benutzeroberfläche (Deutsch/Englisch).
*   Anpassbare Parameter in den erweiterten Einstellungen:
    *   EAR-Schwellenwerte (Empfindlichkeit der Blinzelerkennung).
    *   Gewünschte Kameraauflösung und FPS.
    *   Verarbeitungsintervall (um CPU-Last zu reduzieren).
*   Logging von Ereignissen und Fehlern in die Datei `eye_tracker_log.txt`.
*   Modernes UI-Theme dank `ttkbootstrap`.

## Voraussetzungen

*   Python 3.x
*   Eine angeschlossene Webcam
*   Die folgenden Python-Bibliotheken:
    *   `opencv-python`
    *   `mediapipe`
    *   `numpy`
    *   `pydirectinput` (für die Tastatursimulation)
    *   `ttkbootstrap` (für die GUI)
    *   `Pillow` (PIL) (Abhängigkeit von ttkbootstrap/Bildverarbeitung)
    *   `pygrabber` (Optional, nur für Windows, um bessere Kameranamen anzuzeigen)

## Installation

1.  **Klone das Repository:**
    ```bash
    git clone <URL-ZU-DEINEM-REPOSITORY>
    cd LockdownEyeProtocol # Oder wie dein Verzeichnis heißt
    ```
2.  **(Optional aber empfohlen) Erstelle eine virtuelle Umgebung:**
    ```bash
    python -m venv venv
    # Windows:
    .\venv\Scripts\activate
    # Linux/macOS:
    source venv/bin/activate
    ```
3.  **Installiere die Abhängigkeiten:**
    ```bash
    pip install opencv-python mediapipe numpy pydirectinput ttkbootstrap Pillow pygrabber
    ```
    *(Hinweis: `pygrabber` ist nur für Windows relevant, verursacht aber auf anderen Systemen keine Probleme, wenn es installiert ist.)*

## Benutzung

1.  Stelle sicher, dass deine Webcam angeschlossen ist und von deinem System erkannt wird.
2.  Führe das Skript über deine Konsole oder IDE aus:
    ```bash
    python LockdownEyetracker.py
    ```
3.  Die Anwendung startet. Wähle die gewünschte Webcam aus der Dropdown-Liste oben aus.
4.  Passe bei Bedarf die Sprache oder andere Optionen (Vorschau, Overlay) an.
5.  Klicke auf **"▶ Start"**, um das Tracking zu beginnen.
6.  Die Anwendung versucht nun, dein Gesicht zu finden und die Augen zu verfolgen. Die Statusanzeige zeigt den aktuellen Zustand.
7.  Blinzeln löst jetzt Tastatureingaben gemäß der Standardbelegung aus (siehe unten).
8.  Klicke auf **"■ Stop"**, um das Tracking zu beenden.
9.  Klicke auf **"❌ Exit"**, um die Anwendung zu schließen.

**Wichtiger Hinweis für Windows-Nutzer:** Wenn du Tastatureingaben in Spielen oder anderen Anwendungen simulieren möchtest, die erhöhte Rechte benötigen, musst du das Python-Skript möglicherweise **"Als Administrator ausführen"**.

## Tastaturbelegung (Standard)

Die folgenden Aktionen werden standardmäßig ausgelöst:

*   **Nur linkes Auge geschlossen halten:** Hält die Taste `x` gedrückt, bis das Auge wieder geöffnet wird.
*   **Nur rechtes Auge geschlossen halten:** Hält die Taste `c` gedrückt, bis das Auge wieder geöffnet wird.
*   **Beide Augen gleichzeitig schließen:** Drückt kurz die Tasten `x` und `c` gleichzeitig (einmaliger Tastendruck).
*   **Beide Augen öffnen (nachdem beide geschlossen waren):** Drückt kurz die Taste `x` (einmaliger Tastendruck).

## Konfiguration

Über die grafische Oberfläche kannst du verschiedene Aspekte anpassen:

*   **Vorschau / Overlay:** Schalte die Live-Kameravorschau und das Gesichtsnetz-Overlay im Vorschaufenster ein oder aus.
*   **Sprache:** Wechsle die Sprache der Benutzeroberfläche zwischen Deutsch und Englisch.
*   **Erweiterte Einstellungen (Klick auf ⚙️):**
    *   **EAR Schließen/Öffnen:** Passe die Schwellenwerte für die Blinzelerkennung an (Eye Aspect Ratio). Niedrigere Werte für "Schließen" und höhere Werte für "Öffnen" machen die Erkennung empfindlicher bzw. unempfindlicher. Experimentiere hiermit, falls Blinzeln nicht gut erkannt wird. Es muss gelten: `0 < CLOSE < OPEN < 1.0`.
    *   **Kamera Breite/Höhe/FPS:** Lege die gewünschte Auflösung und Bildwiederholrate für deine Kamera fest. Beachte, dass nicht alle Kameras alle Kombinationen unterstützen. Änderungen hier erfordern oft einen Neustart des Trackings oder der Vorschau (`Stop` -> `Start`).
    *   **Frame Intervall:** Bestimmt, wie viele Frames übersprungen werden, bevor eine Analyse stattfindet. Ein Wert von `1` analysiert jeden Frame (höchste Genauigkeit, höchste CPU-Last). Ein Wert von `2` analysiert jeden zweiten Frame usw. Erhöhe diesen Wert, um die CPU-Last zu senken, was aber die Reaktionszeit leicht verzögern kann.

## Fehlerbehebung / Bekannte Probleme

*   **Prozess bleibt nach "Exit" aktiv:** Manchmal kann der Python-Prozess im Hintergrund weiterlaufen, nachdem du auf "Exit" geklickt hast. Dies liegt meist daran, dass der Kamerazugriff oder die Freigabe der Kamera länger dauert als erwartet und der Thread nicht rechtzeitig beendet wird. Das Skript wartet beim Beenden 5 Sekunden auf die Threads. Sollte das Problem weiterhin auftreten, musst du den Prozess eventuell manuell über den Task-Manager (Windows) oder `kill` (Linux/macOS) beenden.
*   **Keine Tasteneingaben in Spielen (Windows):** Wie oben erwähnt, versuche das Skript `Als Administrator auszuführen`. Manche Spiele blockieren Eingaben von nicht-privilegierten Prozessen.
*   **Falsche Kameranamen / Kamera nicht gefunden:** Stelle sicher, dass die Kamera korrekt angeschlossen ist. Unter Windows hilft die (optionale) `pygrabber`-Bibliothek, korrekte Namen anzuzeigen. Ohne diese werden generische Namen wie "Kamera 0" verwendet.
*   **Ungenauer Augenstatus:** Passe die EAR-Schwellenwerte in den erweiterten Einstellungen an deine Lichtverhältnisse und deine Augen an. Gute Beleuchtung ist generell hilfreich.

## MIT License

Copyright (c) 2023 tcbob1994

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
