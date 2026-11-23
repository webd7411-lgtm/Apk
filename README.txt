FATWA GRABBER - ANDROID APP (APK kaise banayein)
================================================
APK aap ke apne GitHub account par free me banta hai. Computer par Python/Android Studio
install karne ki zaroorat nahi.

STEP 1: GitHub account banao (github.com, free).
STEP 2: Naya repository banao: "New repository" > naam: fatwagrabber > Public ya Private > Create.
STEP 3: Is zip ke andar ki SAARI files repository me upload karo:
        main.py, grabber_core.py, buildozer.spec aur .github folder.
        ("Add file" > "Upload files" me files/folders drag kar do, phir "Commit changes".)
        NOTE: Agar .github folder upload na ho (hidden hone ki wajah se), to
        "Add file" > "Create new file" me naam likho:  .github/workflows/build.yml
        aur build.yml ka content copy-paste kar do.
STEP 4: Repository ke "Actions" tab me jao. "Build APK" chalta nazar aaye ga
        (na chale to Actions > Build APK > "Run workflow").
        Pehli build me 20-40 minute lagte hain.
STEP 5: Build green tick ho jaye to us run ko kholo, neeche "Artifacts" me
        "FatwaGrabber-apk" download karo. Zip me .apk milegi.
STEP 6: APK ko phone me bhejo aur install karo
        (Settings me "Install unknown apps" ki ijazat deni hogi).

APP ISTEMAL KARNA
- Category link(s) paste karo, START dabao.
- Pehli baar storage ki permission mange to Allow karo.
- Download chalte waqt app khuli rakho aur phone charger par lagao. Battery saver band rakho
  (Settings > Apps > Fatwa Grabber > Battery > Unrestricted).
- Mobile par "Ek PDF me fatawa" 100-200 rakho (default 200).
- Kaam khatam hone par PDFs phone ke Download/Fatawa folder me aa jati hain.
- STOP karke dobara START karo to wahin se resume hoga.

AGAR BUILD FAIL HO
Actions me failed run kholo, neeche wale error ke aakhri 30-40 lines copy kar ke mujhe bhejo.
