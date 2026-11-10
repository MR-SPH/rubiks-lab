# Contributing to Rubik's Cube Lab | دليل المساهمة في مختبر مكعب روبيك

[English](#english) | [العربية](#العربية)

---

<a id="english"></a>
## English

Thank you for your interest in contributing to **Rubik's Cube Lab**! This project is an interactive 3D Rubik's Cube laboratory, solver (LBL & Two-Phase Kociemba), and training workbench built with Python, PySide6, and NumPy.

### How to Contribute

#### 1. Reporting Bugs
- Check the [GitHub Issues](https://github.com/MR-SPH/rubiks-lab/issues) to verify if the bug has already been reported.
- If not, open a new issue describing:
  - Clear steps to reproduce the issue.
  - Expected vs. actual behavior.
  - Operating system and Python version.
  - Any error tracebacks or screenshots.

#### 2. Suggesting Features
- Open an issue tagged as `enhancement`.
- Describe the proposed feature, user value, and technical implementation idea.

#### 3. Submitting Pull Requests (PR)
1. Fork the repository and clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/rubiks-lab.git
   cd rubiks-lab
   ```
2. Create a dedicated feature or bugfix branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Set up a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate       # On Windows
   # source .venv/bin/activate    # On Linux/macOS
   pip install -r requirements.txt
   ```
4. Make your changes adhering to project architectural rules:
   - **Single Source of Truth**: Keep cube state integers in `core/cube.py`.
   - **Decoupled 3D Engine**: 3D math and rendering in `engine/`, free of Qt widget logic.
   - **UI Separation**: PySide6 views in `ui/`.
5. Run the test suite and ensure all tests pass:
   ```bash
   pytest
   ```
6. Commit your changes following clear commit conventions:
   ```bash
   git commit -m "feat: add support for custom scramble generators"
   ```
7. Push your branch and submit a Pull Request to `main`.

### Code of Conduct
Please be respectful and constructive in all discussions, issues, and code reviews.

---

<a id="العربية"></a>
## العربية

شكراً لاهتمامك بالمساهمة في مشروع **Rubik's Cube Lab**! هذا المشروع عبارة عن بيئة تفاعلية ثلاثية الأبعاد لمكعب روبيك، وحل تلقائي بخوارزميات (LBL و Two-Phase Kociemba)، ونظام تدريب وإحصائيات تم بناؤه باستخدام Python و PySide6 و NumPy.

### كيفية المساهمة

#### 1. الإبلاغ عن الأخطاء (Bug Reports)
- تأكد أولاً من قائمة [المشكلات (Issues)](https://github.com/MR-SPH/rubiks-lab/issues) للتحقق من عدم الإبلاغ عن المشكلة مسبقاً.
- في حال كانت المشكلة جديدة، افتح Issue جديد موضحاً:
  - خطوات تكرار المشكلة بوضوح.
  - السلوك المتوقع مقابل السلوك الفعلي الذي حدث.
  - نظام التشغيل وإصدار بايثون المستخدم.
  - لقطات شاشة أو سجل الخطأ (Traceback) إن وُجد.

#### 2. اقتراح ميزات جديدة (Feature Suggestions)
- قم بفتح Issue وصنّفه كـ `enhancement`.
- اشرح الميزة المقترحة وفائدتها التقنية أو العملية للمستخدم.

#### 3. إرسال طلبات السحب (Pull Requests - PR)
1. اعمل Fork للمستودع ثم انسخه إلى جهازك:
   ```bash
   git clone https://github.com/YOUR_USERNAME/rubiks-lab.git
   cd rubiks-lab
   ```
2. أنشئ فرعاً جديداً خاصاً بالميزة أو الإصلاح:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. أنشئ البيئة الافتراضية وثبّت الحزم المطلوبة:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate       # لنظام ويندوز
   # source .venv/bin/activate    # لنظام لينكس وماك
   pip install -r requirements.txt
   ```
4. قم بإجراء تعديلاتك مع الالتزام بالمعايير الهيكلية للمشروع:
   - **مصدر الحقيقة الموحد**: حفظ حالات المكعب كأرقام صحيحة داخل `core/cube.py`.
   - **فصل محرك الأبعاد الثلاثية**: معادلات العرض في `engine/` مستقلة عن منطق عناصر Qt.
   - **فصل واجهة المستخدم**: تصميم الواجهات والأزرار في `ui/`.
5. شغّل حزمة الاختبارات وتأكد من نجاحها جميعاً:
   ```bash
   pytest
   ```
6. احفظ التعديلات (Commit) برسالة واضحة:
   ```bash
   git commit -m "feat: add support for custom scramble generators"
   ```
7. ارفع الفرع الخاص بك وأرسل Pull Request إلى فرع `main`.

### ميثاق السلوك (Code of Conduct)
نرجو الالتزام بالاحترام المتبادل والتعاون البنّاء في جميع النقاشات ومراجعات الكود.
