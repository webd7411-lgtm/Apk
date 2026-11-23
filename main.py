# -*- coding: utf-8 -*-
import os, threading
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.utils import platform
from grabber_core import Grabber

KV = """
BoxLayout:
    orientation: 'vertical'
    padding: dp(10)
    spacing: dp(6)
    Label:
        text: 'Fatwa Grabber'
        font_size: '20sp'
        bold: True
        size_hint_y: None
        height: dp(36)
    Label:
        text: 'Category links (har line me ek):'
        size_hint_y: None
        height: dp(22)
        text_size: self.size
        halign: 'left'
    TextInput:
        id: urls
        text: 'https://www.fatwaqa.com/ur/fatawa/quran-aur-hadees'
        size_hint_y: None
        height: dp(90)
        hint_text: 'https://www.fatwaqa.com/ur/fatawa/...'
    BoxLayout:
        size_hint_y: None
        height: dp(42)
        spacing: dp(6)
        Label:
            text: 'Ek PDF me fatawa:'
            text_size: self.size
            halign: 'left'
            valign: 'middle'
        TextInput:
            id: vol
            text: '200'
            multiline: False
            input_filter: 'int'
            size_hint_x: 0.35
        Label:
            text: 'Speed (1-5):'
        TextInput:
            id: wk
            text: '3'
            multiline: False
            input_filter: 'int'
            size_hint_x: 0.2
    BoxLayout:
        size_hint_y: None
        height: dp(48)
        spacing: dp(8)
        Button:
            id: start
            text: 'START'
            background_color: 0.04, 0.35, 0.42, 1
            on_release: app.start()
        Button:
            id: stop
            text: 'STOP'
            disabled: True
            on_release: app.stop_it()
    ProgressBar:
        id: bar
        max: 100
        size_hint_y: None
        height: dp(14)
    Label:
        id: status
        text: 'Tayyar'
        size_hint_y: None
        height: dp(22)
    ScrollView:
        id: sv
        do_scroll_x: False
        Label:
            id: logbox
            text: ''
            size_hint_y: None
            height: self.texture_size[1]
            text_size: self.width, None
            halign: 'left'
            valign: 'top'
            font_size: '12sp'
"""


def app_dir():
    if platform == 'android':
        try:
            from jnius import autoclass
            act = autoclass('org.kivy.android.PythonActivity').mActivity
            d = act.getExternalFilesDir(None)
            if d is not None:
                return d.getAbsolutePath()
        except Exception:
            pass
    return App.get_running_app().user_data_dir


def publish_to_downloads(path, log):
    """PDF ko phone ke Download/Fatawa folder me copy karta hai."""
    name = os.path.basename(path)
    try:
        from jnius import autoclass
        sdk = autoclass('android.os.Build$VERSION').SDK_INT
        act = autoclass('org.kivy.android.PythonActivity').mActivity
        if sdk >= 29:
            CV = autoclass('android.content.ContentValues')
            Dl = autoclass('android.provider.MediaStore$Downloads')
            MC = autoclass('android.provider.MediaStore$MediaColumns')
            v = CV()
            v.put(MC.DISPLAY_NAME, name)
            v.put(MC.MIME_TYPE, 'application/pdf')
            v.put(MC.RELATIVE_PATH, 'Download/Fatawa')
            res = act.getContentResolver()
            uri = res.insert(Dl.EXTERNAL_CONTENT_URI, v)
            out = res.openOutputStream(uri)
            File = autoclass('java.io.File')
            Files = autoclass('java.nio.file.Files')
            Files.copy(File(path).toPath(), out)
            out.close()
        else:
            import shutil
            Env = autoclass('android.os.Environment')
            base = Env.getExternalStoragePublicDirectory(Env.DIRECTORY_DOWNLOADS).getAbsolutePath()
            os.makedirs(os.path.join(base, 'Fatawa'), exist_ok=True)
            shutil.copy(path, os.path.join(base, 'Fatawa', name))
        log(f"Download/Fatawa me copy hua: {name}")
    except Exception as e:
        log(f"Download me copy nahi hua ({name}): {e}\nFile yahan hai: {path}")


class FatwaApp(App):
    title = 'Fatwa Grabber'

    def build(self):
        self.stop_ev = threading.Event()
        self.lines = []
        self.wl = None
        self.root_w = Builder.load_string(KV)
        return self.root_w

    def on_start(self):
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([Permission.WRITE_EXTERNAL_STORAGE,
                                     Permission.READ_EXTERNAL_STORAGE])
            except Exception:
                pass

    # ----- thread-safe UI helpers -----
    def log(self, msg):
        Clock.schedule_once(lambda dt: self._log(msg))

    def _log(self, msg):
        self.lines.append(str(msg))
        self.lines = self.lines[-250:]
        ids = self.root_w.ids
        ids.logbox.text = "\n".join(self.lines)
        Clock.schedule_once(lambda dt: setattr(ids.sv, 'scroll_y', 0), 0.05)

    def progress(self, done, total):
        def f(dt):
            ids = self.root_w.ids
            ids.bar.value = (done / total * 100) if total else 0
            ids.status.text = f"{done} / {total}"
        Clock.schedule_once(f)

    def _set_running(self, running):
        def f(dt):
            ids = self.root_w.ids
            ids.start.disabled = running
            ids.stop.disabled = not running
        Clock.schedule_once(f)

    # ----- wakelock -----
    def _wake(self, on):
        if platform != 'android':
            return
        try:
            from jnius import autoclass
            act = autoclass('org.kivy.android.PythonActivity').mActivity
            if on:
                pm = act.getSystemService('power')
                self.wl = pm.newWakeLock(1, 'fatwa:grab')
                self.wl.acquire()
            elif self.wl is not None:
                self.wl.release()
                self.wl = None
        except Exception as e:
            self.log(f"wakelock: {e}")

    # ----- actions -----
    def start(self):
        ids = self.root_w.ids
        urls = [u.strip() for u in ids.urls.text.splitlines() if u.strip()]
        if not urls:
            self.log("Kam az kam ek category link do.")
            return
        try:
            vol = max(10, int(ids.vol.text or 200))
            wk = min(5, max(1, int(ids.wk.text or 3)))
        except ValueError:
            vol, wk = 200, 3
        self.stop_ev.clear()
        self._set_running(True)
        threading.Thread(target=self._work, args=(urls, vol, wk), daemon=True).start()

    def stop_it(self):
        self.stop_ev.set()
        self.log("Ruk raha hai...")

    def _work(self, urls, vol, wk):
        self._wake(True)
        try:
            out = os.path.join(app_dir(), "Fatawa")
            self.log(f"Kaam ka folder: {out}")
            g = Grabber(out, self.log, self.progress, self.stop_ev,
                        delay=1.0, workers=wk, volume=vol)
            g.run(urls)
            mdir = os.path.join(out, "PDF_volumes")
            if os.path.isdir(mdir) and platform == 'android':
                for fn in sorted(os.listdir(mdir)):
                    if fn.endswith(".pdf"):
                        publish_to_downloads(os.path.join(mdir, fn), self.log)
            elif os.path.isdir(mdir):
                self.log(f"PDFs yahan hain: {mdir}")
        except Exception as e:
            self.log(f"ERROR: {e}")
        finally:
            self._wake(False)
            self._set_running(False)


if __name__ == '__main__':
    FatwaApp().run()
