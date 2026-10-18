"""US7: Step-by-Step Admission Guide Service.

Provides structured, localized step-by-step admission roadmaps for:
- Domestic (Kazakhstani) and International applicants
- Undergraduate (Bachelor) and Graduate (Master) programs
- Localized in Russian (ru), Kazakh (kk/kz), and English (en)
"""
from typing import Dict, List, Any


GUIDE_DATA = {
    ("domestic", "undergraduate"): {
        "ru": [
            {
                "step": 1,
                "title": "ЕНТ и выбор профильных предметов",
                "timeline": "Январь – Июнь",
                "description": (
                    "Сдача Единого национального тестирования (ЕНТ). Выбор двух профильных "
                    "предметов в зависимости от желаемой образовательной программы SDU. "
                    "Минимальный проходной порог для SDU: от 50 баллов (общий), "
                    "65 баллов (педагогические и соц. науки), 75 баллов (IT и юриспруденция). "
                    "Каждый предмет — не менее 5 баллов."
                ),
                "tips": "Следите за графиком Национального центра тестирования (testcenter.kz)."
            },
            {
                "step": 2,
                "title": "Подача на государственный грант РК или олимпиаду SDU SPT",
                "timeline": "Январь – Март (SPT) / 13 – 20 июля (Госгрант)",
                "description": (
                    "Участие в республиканской олимпиаде SDU SPT для получения внутренних грантов "
                    "и скидок (до 100% на 4 года). Подача заявления на Республиканский конкурс "
                    "государственных грантов через eGov или приемную комиссию SDU с 13 по 20 июля."
                ),
                "tips": "Участие в олимпиаде SPT бесплатное (spt.sdu.edu.kz)."
            },
            {
                "step": 3,
                "title": "Онлайн или офлайн подача документов в SDU",
                "timeline": "20 июня – 25 августа",
                "description": (
                    "Регистрация на портале приемной комиссии SDU (admissions.sdu.edu.kz) или "
                    "личный визит в кампус SDU (г. Каскелен). Подача пакета документов: "
                    "аттестат/диплом, сертификат ЕНТ, удостоверение личности, медсправка 075-У, "
                    "карта прививок 063-У, 6 фото 3х4."
                ),
                "tips": "Загрузите сканы заранее для ускорения очной верификации."
            },
            {
                "step": 4,
                "title": "Подтверждение английского языка (IELTS 5.5+ или внутренний тест SDU)",
                "timeline": "Июль – Август",
                "description": (
                    "Предоставление международного сертификата IELTS (минимум 5.5) / TOEFL iBT (46+) "
                    "для освобождения от подготовительного языкового курса Foundation. "
                    "При отсутствии сертификата — сдача внутреннего теста SDU Proficiency Exam (Level B1+). "
                    "Студенты с недостаточным уровнем зачисляются на интенсивный курс Foundation English."
                ),
                "tips": "Оригинал или электронный сертификат IELTS проверяется онлайн."
            },
            {
                "step": 5,
                "title": "Подписание договора и оплата первого взноса (50%)",
                "timeline": "До 25 августа",
                "description": (
                    "Заключение двустороннего договора на обучение в SDU. Для платного отделения — "
                    "оплата первого взноса в размере не менее 50% от годовой стоимости обучения. "
                    "Все первокурсники (включая обладателей грантов) также оплачивают обязательный "
                    "разовый студенческий сбор при регистрации (~60 000 KZT)."
                ),
                "tips": "Вторая часть годовой оплаты вносится до начала весеннего семестра."
            },
            {
                "step": 6,
                "title": "Подача заявления на общежитие и регистрация на дисциплины (Portal)",
                "timeline": "10 – 28 августа",
                "description": (
                    "Подача онлайн-заявки на место в студенческом общежитии через личный кабинет (Portal). "
                    "Приоритет предоставляется иногородним первокурсникам. Получение студенческого логина/пароля, "
                    "выбор академических дисциплин (20–42 ECTS) и составление персонального расписания."
                ),
                "tips": "Места в общежитии распределяются в порядке подачи заявок в августе."
            }
        ],
        "kk": [
            {
                "step": 1,
                "title": "ҰБТ және бейіндік пәндерді таңдау",
                "timeline": "Қаңтар – Маусым",
                "description": (
                    "Ұлттық бірыңғай тестілеуді (ҰБТ) тапсыру. SDU бағдарламаларына сәйкес "
                    "екі бейіндік пәнді таңдау. SDU-ға түсу үшін шекті балдар: кемінде 50 балл "
                    "(жалпы), 65 балл (педагогика және әлеуметтік ғылымдар), 75 балл (IT және заң). "
                    "Әр пән бойынша кемінде 5 балл жинау қажет."
                ),
                "tips": "Ұлттық тестілеу орталығының кестесін қадағалаңыз (testcenter.kz)."
            },
            {
                "step": 2,
                "title": "ҚР мемлекеттік грантына немесе SDU SPT олимпиадасына өтініш беру",
                "timeline": "Қаңтар – Наурыз (SPT) / 13 – 20 шілде (Мемлекеттік грант)",
                "description": (
                    "SDU ішкі гранттары мен 100%-ға дейінгі жеңілдіктерін ұтып алу үшін жыл сайынғы "
                    "SDU SPT олимпиадасына қатысу. 13–20 шілде аралығында eGov порталы немесе "
                    "SDU қабылдау комиссиясы арқылы мемлекеттік гранттар байқауына өтініш беру."
                ),
                "tips": "SPT олимпиадасына қатысу тегін (spt.sdu.edu.kz)."
            },
            {
                "step": 3,
                "title": "SDU-ға құжаттарды онлайн немесе офлайн тапсыру",
                "timeline": "20 маусым – 25 тамыз",
                "description": (
                    "SDU қабылдау комиссиясының порталында тіркелу (admissions.sdu.edu.kz) немесе "
                    "SDU кампусына келу (Қаскелең қ.). Құжаттар топтамасын өткізу: "
                    "аттестат/диплом, ҰБТ сертификаты, жеке куәлік көшірмесі, 075-У медициналық анықтамасы, "
                    "063-У егу картасы, 3х4 өлшемді 6 фотосурет."
                ),
                "tips": "Құжаттардың сканерленген нұсқаларын алдын ала жүктеңіз."
            },
            {
                "step": 4,
                "title": "Ағылшын тілін растау (IELTS 5.5+ немесе SDU ішкі емтиханы)",
                "timeline": "Шілде – Тамыз",
                "description": (
                    "Foundation дайындық жылынан босатылу үшін халықаралық IELTS (кемінде 5.5) / "
                    "TOEFL iBT (46+) сертификатын ұсыну. Сертификат болмаған жағдайда SDU Proficiency Exam "
                    "(Level B1+) ішкі емтиханын тапсыру. Деңгейі жеткіліксіз студенттер Foundation English "
                    "дайындық курсына қабылданады."
                ),
                "tips": "IELTS сертификаты онлайн тексеріледі."
            },
            {
                "step": 5,
                "title": "Шартқа қол қою және алғашқы жарнаны төлеу (50%)",
                "timeline": "25 тамызға дейін",
                "description": (
                    "SDU-мен оқу шартын жасасу. Ақылы бөлімге түсушілер үшін оқу ақысының кемінде "
                    "50%-ын төлеу. Барлық бірінші курс студенттері (соның ішінде грант иегерлері) "
                    "біржолғы студенттік тіркеу жарнасын (~60 000 KZT) төлейді."
                ),
                "tips": "Оқу ақысының екінші бөлігі көктемгі семестрге дейін төленеді."
            },
            {
                "step": 6,
                "title": "Жатақханаға өтініш беру және пәндерге тіркелу (Portal)",
                "timeline": "10 – 28 тамыз",
                "description": (
                    "Студенттік портал (Portal) арқылы жатақханаға онлайн өтініш жолдау. "
                    "Басымдық өңірлерден келген бірінші курс студенттеріне беріледі. Студенттік "
                    "логин/пароль алу, академиялық пәндерді таңдау (20–42 ECTS) және жеке кесте құру."
                ),
                "tips": "Жатақхана орындары тамыз айында өтініш беру кезектілігімен бөлінеді."
            }
        ],
        "en": [
            {
                "step": 1,
                "title": "UNT and Selection of Profile Subjects",
                "timeline": "January – June",
                "description": (
                    "Pass the Unified National Testing (UNT). Select two profile subjects according "
                    "to the desired SDU undergraduate degree program. Minimum threshold score for SDU: "
                    "50 points (general), 65 points (pedagogical & social sciences), 75 points (IT & Law). "
                    "At least 5 points in each test subject."
                ),
                "tips": "Follow updates on the National Testing Center portal (testcenter.kz)."
            },
            {
                "step": 2,
                "title": "Apply for Kazakhstan State Grant or SDU SPT Olympiad",
                "timeline": "January – March (SPT) / July 13 – 20 (State Grant)",
                "description": (
                    "Participate in the SDU SPT Olympiad to win university internal tuition grants "
                    "and scholarships (up to 100% for 4 years). Apply for the Republic of Kazakhstan "
                    "State Educational Grant competition via eGov portal or SDU Admissions from July 13 to July 20."
                ),
                "tips": "SPT Olympiad participation is completely free (spt.sdu.edu.kz)."
            },
            {
                "step": 3,
                "title": "Online or In-Person Document Submission to SDU",
                "timeline": "June 20 – August 25",
                "description": (
                    "Register on the SDU Admissions Portal (admissions.sdu.edu.kz) or visit the SDU campus "
                    "in Kaskelen. Submit required documents: secondary school certificate/diploma with transcript, "
                    "UNT certificate, national ID card copy, medical form 075-U, vaccination form 063-U, "
                    "and six 3x4 photos."
                ),
                "tips": "Pre-upload scanned documents to accelerate verification."
            },
            {
                "step": 4,
                "title": "English Proficiency Verification (IELTS 5.5+ or SDU Internal Exam)",
                "timeline": "July – August",
                "description": (
                    "Provide an international IELTS (minimum 5.5) or TOEFL iBT (46+) certificate "
                    "to be exempted from the English Foundation year. Applicants without a certificate "
                    "must pass the SDU English Proficiency Exam (Level B1+). Those who score below the cutoff "
                    "enroll in the intensive 1-year SDU Foundation English course."
                ),
                "tips": "IELTS certificates are verified electronically via the TRF portal."
            },
            {
                "step": 5,
                "title": "Contract Signing and Initial Deposit Payment (50%)",
                "timeline": "Until August 25",
                "description": (
                    "Sign the official educational contract with SDU. For fee-paying students, make "
                    "an initial deposit payment of at least 50% of the annual tuition fee. "
                    "All first-year students (including grant recipients) pay the mandatory one-time "
                    "student registration fee (~60,000 KZT)."
                ),
                "tips": "The second semester tuition payment is due before the spring term begins."
            },
            {
                "step": 6,
                "title": "Dormitory Application and Course Registration (Portal)",
                "timeline": "August 10 – 28",
                "description": (
                    "Submit an online application for accommodation in modern on-campus student dormitories "
                    "via the student portal. Priority is granted to regional first-year students. "
                    "Obtain university portal credentials, select academic courses (20–42 ECTS), and build schedule."
                ),
                "tips": "Dormitory rooms are allocated on a first-come, first-served basis in August."
            }
        ]
    },
    ("international", "undergraduate"): {
        "ru": [
            {
                "step": 1,
                "title": "Выбор программы и подача онлайн-заявки",
                "timeline": "Март – Июль",
                "description": (
                    "Иностранные абитуриенты освобождены от сдачи ЕНТ. Заполните онлайн-анкету "
                    "на портале admissions.sdu.edu.kz или свяжитесь с международным отделом (intadmissions@sdu.edu.kz). "
                    "Предоставьте скан паспорта и табеля/аттестата об окончании школы."
                ),
                "tips": "Результаты SAT или ACT приветствуются и дают преимущество."
            },
            {
                "step": 2,
                "title": "Онлайн-интервью и академическое рассмотрение",
                "timeline": "Апрель – Август",
                "description": (
                    "Прохождение онлайн-собеседования с приемной комиссией и факультетом. "
                    "Оценка успеваемости (GPA), мотивации и владения языком. "
                    "Рассмотрение заявки на получение международной стипендии SDU."
                ),
                "tips": "Подготовьте краткое мотивационное письмо."
            },
            {
                "step": 3,
                "title": "Подтверждение английского языка (IELTS 5.5+ или тест SDU)",
                "timeline": "Май – Август",
                "description": (
                    "Предоставление сертификата IELTS 5.5+ / TOEFL 46+ или сдача онлайн-теста SDU. "
                    "При уровне ниже B1 студент проходит годичную программу SDU Foundation English."
                ),
                "tips": "Для англоязычных программ сертификат освобождает от подготовительного курса."
            },
            {
                "step": 4,
                "title": "Договор, оплата депозита и получение приглашения на визу (C9)",
                "timeline": "Июнь – Август",
                "description": (
                    "Подписание договора, оплата первого семестра (50% годовой стоимости) и регистрационного сбора. "
                    "SDU оформляет официальное письмо-приглашение и номер визовой поддержки для студенческой визы C9."
                ),
                "tips": "Оформление визовой поддержки занимает от 2 до 4 недель."
            },
            {
                "step": 5,
                "title": "Нострификация документов и прибытие в кампус",
                "timeline": "Август – Сентябрь",
                "description": (
                    "Нотариально заверенный перевод документов на казахский/русский язык. "
                    "Прохождение государственной процедуры признания (нострификации) зарубежного аттестата в РК. "
                    "Медицинский осмотр и регистрация в миграционных органах."
                ),
                "tips": "Международный отдел SDU курирует весь процесс нострификации."
            },
            {
                "step": 6,
                "title": "Заселение в общежитие и регистрация на курсы",
                "timeline": "20 – 31 августа",
                "description": (
                    "Иностранным студентам гарантируется приоритетное место в общежитии на кампусе SDU. "
                    "Ориентационная неделя (Orientation Week), открытие банковской карты и выбор предметов на портале."
                ),
                "tips": "На кампусе работает служба кураторов для адаптации иностранных студентов."
            }
        ],
        "en": [
            {
                "step": 1,
                "title": "Program Selection and Online Application",
                "timeline": "March – July",
                "description": (
                    "International applicants are exempt from the UNT exam. Fill out the application "
                    "at admissions.sdu.edu.kz or contact intadmissions@sdu.edu.kz. Upload your passport "
                    "and official high school transcript/diploma."
                ),
                "tips": "SAT or ACT scores are welcome and provide scholarship advantages."
            },
            {
                "step": 2,
                "title": "Online Interview and Academic Review",
                "timeline": "April – August",
                "description": (
                    "Participate in an admissions interview with faculty members. Evaluation of high school "
                    "GPA, motivation, and eligibility for international merit-based scholarships."
                ),
                "tips": "Prepare a concise statement of purpose."
            },
            {
                "step": 3,
                "title": "English Proficiency Verification",
                "timeline": "May – August",
                "description": (
                    "Submit IELTS 5.5+ / TOEFL iBT 46+ or take SDU's online English test. "
                    "Applicants below the required level are placed into SDU Foundation English for one year."
                ),
                "tips": "Exemption directly places you into year 1 of the undergraduate degree."
            },
            {
                "step": 4,
                "title": "Contract, Deposit Payment, and C9 Student Visa Invitation",
                "timeline": "June – August",
                "description": (
                    "Sign the educational agreement, pay 50% semester deposit plus the student fee. "
                    "SDU issues an official visa invitation letter and reference number for the C9 study visa."
                ),
                "tips": "Visa support processing takes approximately 2–4 weeks."
            },
            {
                "step": 5,
                "title": "Document Nostrification and Campus Arrival",
                "timeline": "August – September",
                "description": (
                    "Provide notarized translations of your educational certificate. Complete state diploma "
                    "recognition (nostrification) in Kazakhstan with assistance from SDU International Office."
                ),
                "tips": "SDU International Office assists with all local registration and legal procedures."
            },
            {
                "step": 6,
                "title": "Dormitory Check-in and Course Enrollment",
                "timeline": "August 20 – 31",
                "description": (
                    "International students receive guaranteed priority dormitory placement on the Kaskelen campus. "
                    "Participate in International Student Orientation Week, obtain local SIM/bank card, and register for classes."
                ),
                "tips": "Campus mentors assist with city and campus orientation."
            }
        ],
        "kk": [
            {
                "step": 1,
                "title": "Бағдарламаны таңдау және онлайн өтініш беру",
                "timeline": "Наурыз – Шілде",
                "description": (
                    "Шетелдік талапкерлер ҰБТ тапсырудан босатылған. admissions.sdu.edu.kz порталында "
                    "өтініш толтырыңыз немесе intadmissions@sdu.edu.kz поштасына жазыңыз. "
                    "Төлқұжат пен мектеп аттестатының көшірмесін ұсыныңыз."
                ),
                "tips": "SAT немесе ACT нәтижелері артықшылық береді."
            },
            {
                "step": 2,
                "title": "Онлайн сұхбат және академиялық іріктеу",
                "timeline": "Сәуір – Тамыз",
                "description": (
                    "Қабылдау комиссиясымен онлайн сұхбаттасу. GPA үлгерімін, уәждемені "
                    "және халықаралық шәкіртақы алу мүмкіндігін бағалау."
                ),
                "tips": "Қысқаша уәждемелік хат дайындаңыз."
            },
            {
                "step": 3,
                "title": "Ағылшын тілін растау",
                "timeline": "Мамыр – Тамыз",
                "description": (
                    "IELTS 5.5+ / TOEFL 46+ сертификатын ұсыну немесе SDU онлайн емтиханын тапсыру. "
                    "Деңгейі жеткіліксіз талапкерлер 1 жылдық Foundation курсына жіберіледі."
                ),
                "tips": "Сертификат Foundation дайындық жылынан босатады."
            },
            {
                "step": 4,
                "title": "Шарт, алғашқы төлем және C9 студенттік виза шақыруы",
                "timeline": "Маусым – Тамыз",
                "description": (
                    "Оқу шартына қол қою, бірінші семестр ақысын (50%) және тіркеу жарнасын төлеу. "
                    "SDU C9 студенттік визасын алу үшін ресми шақырту мен қолдау нөмірін рәсімдейді."
                ),
                "tips": "Визалық шақыру 2–4 апта көлемінде дайындалады."
            },
            {
                "step": 5,
                "title": "Құжаттарды нострификациялау және кампусқа келу",
                "timeline": "Тамыз – Қыркүйек",
                "description": (
                    "Білім туралы құжаттарды нотариалды куәландырылған қазақ/орыс тіліндегі аудармасымен тапсыру. "
                    "ҚР Білім министрлігінде нострификация (тану) рәсімінен өту. SDU халықаралық бөлімі көмек көрсетеді."
                ),
                "tips": "Халықаралық бөлім барлық заңды рәсімдерді үйлестіреді."
            },
            {
                "step": 6,
                "title": "Жатақханаға орналасу және пәндерге тіркелу",
                "timeline": "20 – 31 тамыз",
                "description": (
                    "Шетелдік студенттерге кампустағы жатақханадан кепілдендірілген орын беріледі. "
                    "Бейімделу апталығына қатысу (Orientation Week), банк картасын ашу және порталда пәндерді таңдау."
                ),
                "tips": "Кампус кураторлары шетелдік талапкерлерге қолдау көрсетеді."
            }
        ]
    },
    ("domestic", "graduate"): {
        "ru": [
            {
                "step": 1,
                "title": "Комплексное тестирование (КТ) и пререквизиты",
                "timeline": "Май – Июль",
                "description": (
                    "Регистрация и сдача Комплексного тестирования магистрантов (КТ) в НЦТ. "
                    "Тест включает иностранный язык, тест на готовность к обучению и профильные дисциплины. "
                    "Проверка соответствия бакалаврского диплома выбранной магистерской специальности."
                ),
                "tips": "Пороговые баллы КТ утверждаются МНВО РК."
            },
            {
                "step": 2,
                "title": "Подача на государственный грант магистратуры",
                "timeline": "10 – 18 августа",
                "description": (
                    "Участие в конкурсе государственных образовательных грантов для магистратуры через НЦТ/eGov "
                    "по результатам КТ."
                ),
                "tips": "Гранты покрывают полную стоимость магистратуры и предоставляют стипендию."
            },
            {
                "step": 3,
                "title": "Подача документов в SDU Graduate School",
                "timeline": "1 – 25 августа",
                "description": (
                    "Подача пакета документов в приемную комиссию SDU: диплом бакалавра с приложением (транскрипт), "
                    "сертификат КТ, удостоверение личности, резюме (CV), 6 фото 3х4, медсправка 075-У."
                ),
                "tips": "При смене профиля может потребоваться освоение пререквизитов."
            },
            {
                "step": 4,
                "title": "Подтверждение английского языка (IELTS 6.0+)",
                "timeline": "Июль – Август",
                "description": (
                    "Предоставление сертификата IELTS (от 6.0) или TOEFL iBT для освобождения от языкового блока КТ "
                    "и подтверждения готовности к обучению на английском языке в магистратуре SDU."
                ),
                "tips": "Сертификат должен быть действителен на момент поступления."
            },
            {
                "step": 5,
                "title": "Подписание договора и оплата обучения (50%)",
                "timeline": "До 28 августа",
                "description": (
                    "Оформление образовательного контракта магистратуры. Оплата первого взноса (50% годовой суммы) "
                    "для платного отделения и обязательного студенческого сбора."
                ),
                "tips": "Возможна оплата по семестрам."
            },
            {
                "step": 6,
                "title": "Утверждение научного направления и регистрация на курсы",
                "timeline": "Конец августа – Начало сентября",
                "description": (
                    "Встреча с координатором магистерской программы, выбор научных дисциплин и регистрация на Portal SDU. "
                    "Определение темы магистерского диссертационного исследования."
                ),
                "tips": "Занятия в магистратуре обычно проходят в вечернее время или по модульному графику."
            }
        ]
    }
}


def get_admission_guide(
    category: str = "domestic",
    level: str = "undergraduate",
    lang: str = "ru"
) -> Dict[str, Any]:
    """Retrieve ordered list of admission procedure steps.

    Args:
        category: 'domestic' | 'international'
        level: 'undergraduate' | 'graduate'
        lang: 'ru' | 'kk' | 'en' (or aliases 'kz')

    Returns:
        Structured admission guide response with metadata and ordered steps.
    """
    category = (category or "domestic").strip().lower()
    if category not in ("domestic", "international"):
        category = "domestic"

    level = (level or "undergraduate").strip().lower()
    if level not in ("undergraduate", "graduate"):
        level = "undergraduate"

    lang = (lang or "ru").strip().lower()
    if lang in ("kz", "kk-kz", "kazakh"):
        lang = "kk"
    elif lang in ("en-us", "english"):
        lang = "en"
    elif lang in ("ru-ru", "russian"):
        lang = "ru"
    if lang not in ("ru", "kk", "en"):
        lang = "ru"

    key = (category, level)
    # Fallback to (domestic, undergraduate) if specific pair is not found
    guide_dict = GUIDE_DATA.get(key) or GUIDE_DATA.get(("domestic", "undergraduate"))
    # Fallback language to 'ru' if translation not present
    steps = guide_dict.get(lang) or guide_dict.get("ru")

    category_labels = {
        "ru": {"domestic": "Граждане РК (местные)", "international": "Иностранные абитуриенты"},
        "kk": {"domestic": "ҚР азаматтары (отандық)", "international": "Шетелдік талапкерлер"},
        "en": {"domestic": "Domestic Applicants (Kazakhstan)", "international": "International Applicants"},
    }
    level_labels = {
        "ru": {"undergraduate": "Бакалавриат", "graduate": "Магистратура"},
        "kk": {"undergraduate": "Бакалавриат", "graduate": "Магистратура"},
        "en": {"undergraduate": "Undergraduate (Bachelor)", "graduate": "Graduate (Master)"},
    }

    t_cat = category_labels.get(lang, category_labels["ru"]).get(category, category)
    t_lvl = level_labels.get(lang, level_labels["ru"]).get(level, level)

    return {
        "category": category,
        "level": level,
        "language": lang,
        "title": f"SDU University Admission Roadmap: {t_cat} · {t_lvl}",
        "total_steps": len(steps),
        "steps": steps,
        "official_admissions_portal": "https://admissions.sdu.edu.kz",
        "contacts": {
            "call_center": "+7 (727) 307 95 65",
            "whatsapp": "https://wa.me/77020001133",
            "email": "admission@sdu.edu.kz" if category == "domestic" else "intadmissions@sdu.edu.kz"
        }
    }
