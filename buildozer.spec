[app]
title = Fatwa Grabber
package.name = fatwagrabber
package.domain = com.skycode
source.dir = .
source.include_exts = py
version = 1.0
requirements = python3,kivy==2.3.0,requests,urllib3,idna,certifi,charset-normalizer,beautifulsoup4,soupsieve,typing_extensions,pypdf,pillow
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WAKE_LOCK,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 26
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
