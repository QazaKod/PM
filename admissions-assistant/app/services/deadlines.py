"""US8: Official Admissions Campaign Deadlines and Academic Calendar Service (2026-2027 intake).

Maintains all official critical milestones:
  1. UNT Early & Main Testing Sessions
  2. SDU SPT Olympiad Registration & Contest
  3. Admissions Office Opening & Application Portal
  4. Special / Creative Examinations
  5. Kazakhstan Republic State Grant Competition
  6. State Grant Winners Announcement
  7. Student Dormitory Application Deadline
  8. Paid Tuition Enrollment & Contract Signing
"""

import calendar
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

# Almaty timezone
try:
    from zoneinfo import ZoneInfo
    ALMATY_TZ = ZoneInfo("Asia/Almaty")
    datetime.now(ALMATY_TZ)
except Exception:
    from datetime import timezone
    ALMATY_TZ = timezone(timedelta(hours=5))


def local_today() -> date:
    """Returns today's date in Asia/Almaty timezone."""
    return datetime.now(ALMATY_TZ).date()


CATEGORY_COLORS = {
    "grant": "gold",
    "unt": "blue",
    "contract": "green",
    "dormitory": "purple",
    "olympiad": "gold",
    "exam": "red",
}

# Raw master deadline entries for SDU 2026-2027 admissions campaign
OFFICIAL_DEADLINES = [
    {
        "id": "unt_early",
        "date_start": "2026-01-10",
        "date_end": "2026-02-10",
        "category": "unt",
        "degree_level": "undergraduate",
        "action_url": "https://testcenter.kz",
        "i18n": {
            "ru": {
                "title": "ЕНТ: Январское тестирование (платное отделение)",
                "stage_name": "Ранняя регистрация и тестирование ЕНТ",
                "description": "Регистрация и сдача январского ЕНТ для поступления на платное отделение SDU University.",
                "passed_advice": "Если вы пропустили январское ЕНТ, зарегистрируйтесь на мартовское или основное (май-июль) ЕНТ для участия в конкурсе грантов."
            },
            "kk": {
                "title": "ҰБТ: Қаңтардағы тестілеу (ақылы бөлім)",
                "stage_name": "ҰБТ-ға ерте тіркелу және тапсыру",
                "description": "SDU университетінің ақылы бөліміне түсу үшін қаңтар айындағы ҰБТ-ға тіркелу және тестілеу.",
                "passed_advice": "Қаңтар ҰБТ-сынан кешіксеңіз, грант байқауына қатысу үшін наурыз немесе негізгі (мамыр-шілде) ҰБТ-ға тіркеліңіз."
            },
            "en": {
                "title": "UNT Early Testing (Paid Tuition Intake)",
                "stage_name": "UNT Early Registration & Testing",
                "description": "Registration and testing period for January UNT, applicable for fee-paying enrollment at SDU University.",
                "passed_advice": "If you missed the January UNT, register for the March or Main (May-July) UNT sessions to compete for state grants."
            }
        }
    },
    {
        "id": "spt_olympiad",
        "date_start": "2026-01-15",
        "date_end": "2026-03-15",
        "category": "olympiad",
        "degree_level": "undergraduate",
        "action_url": "https://sdu.edu.kz/spt",
        "i18n": {
            "ru": {
                "title": "Олимпиада SDU SPT: Внутренние гранты и скидки",
                "stage_name": "Регистрация и участие в олимпиаде SPT",
                "description": "Ежегодная олимпиада SDU Proficiency Test для выпускников школ. Победители получают 100%, 50%, 30% скидки на все 4 года обучения в SDU.",
                "passed_advice": "Регистрация на SPT завершена. Вы можете претендовать на государственный грант РК или академические скидки SDU за высокие баллы ЕНТ (от 110 баллов)."
            },
            "kk": {
                "title": "SDU SPT Олимпиадасы: Ішкі гранттар мен жеңілдіктер",
                "stage_name": "SPT олимпиадасына тіркелу және өткізу",
                "description": "Мектеп бітірушілерге арналған жыл сайынғы SDU Proficiency Test олимпиадасы. Жеңімпаздарға 4 жылға 100%, 50%, 30% жеңілдіктер беріледі.",
                "passed_advice": "SPT олимпиадасына тіркелу аяқталды. Сіз мемлекеттік грантқа немесе ҰБТ жоғары балдары үшін (110+ балл) берілетін SDU жеңілдіктеріне үміткер бола аласыз."
            },
            "en": {
                "title": "SDU SPT Olympiad: University Grants & Scholarships",
                "stage_name": "SDU SPT Registration & Contest",
                "description": "Annual SDU Proficiency Test for high school graduates. Top performers receive 100%, 50%, and 30% tuition fee discounts for 4 years.",
                "passed_advice": "SPT registration is closed. You can apply for state educational grants or SDU merit discounts for UNT scores >= 110."
            }
        }
    },
    {
        "id": "unt_main",
        "date_start": "2026-05-16",
        "date_end": "2026-07-05",
        "category": "unt",
        "degree_level": "undergraduate",
        "action_url": "https://testcenter.kz",
        "i18n": {
            "ru": {
                "title": "ЕНТ: Основное тестирование (конкурс грантов)",
                "stage_name": "Основной поток сдачи ЕНТ",
                "description": "Сдача основного ЕНТ с правом двух попыток для участия в республиканском конкурсе государственных образовательных грантов.",
                "passed_advice": "Сдача основного ЕНТ завершена. Для поступления на платное отделение обратитесь в приемную комиссию с действующим сертификатом."
            },
            "kk": {
                "title": "ҰБТ: Негізгі тестілеу (мемлекеттік гранттар конкурсы)",
                "stage_name": "Негізгі ҰБТ тапсыру кезеңі",
                "description": "Мемлекеттік білім беру гранттарының республикалық байқауына қатысу үшін негізгі ҰБТ (2 мүмкіндік) тапсыру кезеңі.",
                "passed_advice": "Негізгі ҰБТ аяқталды. Ақылы бөлімге құжат тапсыру үшін қабылдау комиссиясына қолданыстағы сертификатпен хабарласыңыз."
            },
            "en": {
                "title": "UNT Main Testing (State Grant Intake)",
                "stage_name": "UNT Main Testing Session",
                "description": "Main UNT examination period (2 attempts) eligible for the Republic of Kazakhstan State Grant Competition.",
                "passed_advice": "Main UNT testing is closed. Inquire with Admissions regarding paid enrollment eligibility using your existing certificate."
            }
        }
    },
    {
        "id": "admissions_office_open",
        "date_start": "2026-06-20",
        "date_end": "2026-08-25",
        "category": "contract",
        "degree_level": "all",
        "action_url": "https://app.sdu.edu.kz",
        "i18n": {
            "ru": {
                "title": "Открытие Приемной комиссии SDU и онлайн-подача заявок",
                "stage_name": "Старт приема документов и онлайн-регистрация",
                "description": "Официальный старт работы приемной комиссии университета SDU. Подача документов онлайн через портал app.sdu.edu.kz и офлайн в кампусе.",
                "passed_advice": "Основной период работы приемной комиссии завершен. По вопросам поздней подачи обратитесь по почте admission@sdu.edu.kz."
            },
            "kk": {
                "title": "SDU Қабылдау комиссиясының ашылуы және онлайн құжат қабылдау",
                "stage_name": "Құжат қабылдау және онлайн тіркеудің басталуы",
                "description": "SDU университетінің қабылдау комиссиясының ресми басталуы. app.sdu.edu.kz порталы арқылы және кампуста тікелей құжат тапсыру.",
                "passed_advice": "Құжат қабылдау кезеңі аяқталды. Қосымша сұрақтар бойынша admission@sdu.edu.kz поштасына жазыңыз."
            },
            "en": {
                "title": "Admissions Office Opens & Online Applications Launch",
                "stage_name": "Admissions Office Opening & Application Portal",
                "description": "Official launch of SDU Admissions Office. Online application submission via app.sdu.edu.kz and in-person counseling on campus.",
                "passed_advice": "Regular admissions window is closed. For late application inquiries, contact admission@sdu.edu.kz."
            }
        }
    },
    {
        "id": "creative_exams",
        "date_start": "2026-07-05",
        "date_end": "2026-07-15",
        "category": "exam",
        "degree_level": "undergraduate",
        "action_url": "https://admissions.sdu.edu.kz/creative",
        "i18n": {
            "ru": {
                "title": "Специальные и творческие экзамены SDU",
                "stage_name": "Сдача специальных и творческих экзаменов",
                "description": "Сдача творческих экзаменов для программ направления Журналистика и педагогических специальностей (психометрическое тестирование).",
                "passed_advice": "Творческие экзамены проводятся один раз в год. Обратитесь в приемную комиссию для выбора других специальностей без творческого экзамена."
            },
            "kk": {
                "title": "SDU арнайы және шығармашылық емтихандары",
                "stage_name": "Арнайы және шығармашылық емтихандар тапсыру",
                "description": "Журналистика және педагогикалық бағдарламалар (арнайы психометриялық емтихан) бойынша шығармашылық емтихандар тапсыру.",
                "passed_advice": "Шығармашылық емтихандар жылына бір рет өткізіледі. Шығармашылық емтиханды талап етпейтін бағдарламаларды таңдау үшін кеңес алыңыз."
            },
            "en": {
                "title": "Special & Creative Examinations",
                "stage_name": "SDU Creative & Aptitude Exams",
                "description": "Examination window for Journalism and pedagogical degree programs (psychometric & creative portfolio testing).",
                "passed_advice": "Creative examinations are held once per intake. Contact Admissions to explore alternative degree programs without creative exam prerequisites."
            }
        }
    },
    {
        "id": "state_grant_competition",
        "date_start": "2026-07-13",
        "date_end": "2026-07-20",
        "category": "grant",
        "degree_level": "undergraduate",
        "action_url": "https://egov.kz",
        "i18n": {
            "ru": {
                "title": "Конкурс государственных образовательных грантов РК",
                "stage_name": "Подача заявлений на государственный грант",
                "description": "Республиканский прием заявлений на конкурс государственных образовательных грантов через eGov.kz или приемную комиссию SDU (код 045).",
                "passed_advice": "Прием заявлений на грант РК завершен. Вы можете заключить договор на платное обучение в SDU и претендовать на внутренние скидки."
            },
            "kk": {
                "title": "ҚР мемлекеттік білім беру гранттарының байқауы",
                "stage_name": "Мемлекеттік грант байқауына өтініш қабылдау",
                "description": "eGov.kz немесе SDU қабылдау комиссиясы (код 045) арқылы ҚР мемлекеттік білім гранттарының байқауына өтініштер қабылдау.",
                "passed_advice": "Мемлекеттік гранттарға өтініш қабылдау аяқталды. Сіз SDU-дың ақылы бөліміне келісімшарт жасасып, ішкі жеңілдіктерге өтініш бере аласыз."
            },
            "en": {
                "title": "Kazakhstan Republic State Grant Competition",
                "stage_name": "State Grant Application Window",
                "description": "Nationwide application period for Republic of Kazakhstan state educational grants via eGov.kz or SDU Admissions Hub (SDU Code 045).",
                "passed_advice": "State grant applications are closed. You can enroll in fee-paying education and apply for SDU institutional discounts."
            }
        }
    },
    {
        "id": "state_grant_winners",
        "date_start": "2026-08-10",
        "date_end": "2026-08-10",
        "category": "grant",
        "degree_level": "undergraduate",
        "action_url": "https://testcenter.kz",
        "i18n": {
            "ru": {
                "title": "Объявление обладателей государственных грантов",
                "stage_name": "Публикация списка грантников РК",
                "description": "Публикация официального списка обладателей образовательных грантов РК. Поступившие на грант в SDU обязаны подтвердить зачисление до 20 августа.",
                "passed_advice": "Список грантников опубликован. Обладатели грантов должны предоставить оригиналы документов в приемную комиссию SDU."
            },
            "kk": {
                "title": "Мемлекеттік грант иегерлерін жариялау",
                "stage_name": "ҚР грант иегерлері тізімін жариялау",
                "description": "ҚР білім беру гранты иегерлерінің ресми тізімін жариялау. SDU-ға грантқа түскендер 20 тамызға дейін қабылдауды растауы тиіс.",
                "passed_advice": "Грант иегерлерінің тізімі жарияланды. Грант иегерлері түпнұсқа құжаттарын SDU қабылдау комиссиясына тапсыруы қажет."
            },
            "en": {
                "title": "State Grant Winners Announcement",
                "stage_name": "Announcement of State Grant Winners",
                "description": "Official publication of Kazakhstan State Educational Grant recipients. Selected students must confirm enrollment at SDU by August 20.",
                "passed_advice": "Winners list has been published. Grant recipients must submit original documents to SDU Admissions Office."
            }
        }
    },
    {
        "id": "dormitory_application",
        "date_start": "2026-08-01",
        "date_end": "2026-08-20",
        "category": "dormitory",
        "degree_level": "all",
        "action_url": "https://dormitory.sdu.edu.kz",
        "i18n": {
            "ru": {
                "title": "Подача заявлений на студенческое общежитие SDU",
                "stage_name": "Дедлайн приема заявлений в общежитие",
                "description": "Онлайн-подача заявлений на заселение в студенческие дома SDU для иногородних и иностранных студентов 1 курса.",
                "passed_advice": "Основной прием заявлений в общежитие завершен. Подайте заявку в лист ожидания (резерв) через службу размещения: dormitory@sdu.edu.kz."
            },
            "kk": {
                "title": "SDU студенттік жатақханасына өтініш беру",
                "stage_name": "Жатақханаға өтініш қабылдау дедлайны",
                "description": "Басқа қаладан келген және шетелдік 1-курс студенттері үшін SDU студенттік үйлеріне онлайн өтініш беру кезеңі.",
                "passed_advice": "Жатақханаға негізгі өтініш қабылдау аяқталды. Қосымша резервтік тізімге dormitory@sdu.edu.kz арқылы өтініш жіберіңіз."
            },
            "en": {
                "title": "Student Dormitory Application Deadline",
                "stage_name": "Dormitory Housing Application Window",
                "description": "Online application submission for SDU Student Dormitory accommodation for non-local and international freshmen.",
                "passed_advice": "Main dormitory application period is closed. Submit an inquiry for the waiting list via dormitory@sdu.edu.kz."
            }
        }
    },
    {
        "id": "paid_tuition_enrollment",
        "date_start": "2026-08-10",
        "date_end": "2026-08-25",
        "category": "contract",
        "degree_level": "all",
        "action_url": "https://app.sdu.edu.kz",
        "i18n": {
            "ru": {
                "title": "Зачисление на платное отделение и подписание договора",
                "stage_name": "Заключение договоров и оплата первого семестра",
                "description": "Финальный дедлайн заключения договоров возмездного оказания образовательных услуг и внесения первой оплаты за обучение в SDU.",
                "passed_advice": "Срок зачисления и оформления договоров завершен. По вопросам дополнительного набора обратитесь в приемную комиссию."
            },
            "kk": {
                "title": "Ақылы бөлімге қабылдау және келісімшарт жасасу",
                "stage_name": "Келісімшарт бекіту және 1-семестр төлемі",
                "description": "SDU-ға ақылы негізде оқуға түсу үшін келісімшарт жасасудың және 1-ші семестр төлемін жүргізудің соңғы мерзімі.",
                "passed_advice": "Қабылдау және келісімшарт жасасу мерзімі аяқталды. Қосымша қабылдау мәселелері бойынша қабылдау комиссиясына жүгініңіз."
            },
            "en": {
                "title": "Paid Tuition Enrollment & Contract Signing",
                "stage_name": "Contract Signing & First Semester Tuition Payment",
                "description": "Final deadline for tuition contract signing and initial semester fee payment for admitted fee-paying students.",
                "passed_advice": "Enrollment and contract signing period is closed. Inquire with Admissions regarding late admissions appeals."
            }
        }
    },
    {
        "id": "grad_winter_kt_reg",
        "date_start": "2026-10-28",
        "date_end": "2026-11-10",
        "category": "exam",
        "degree_level": "graduate",
        "action_url": "https://app.testcenter.kz",
        "i18n": {
            "ru": {
                "title": "Магистратура (Зимний поток): Регистрация на Комплексное тестирование (КТ)",
                "stage_name": "Прием заявлений на зимнее КТ в магистратуру",
                "description": "Онлайн-регистрация через портал НЦТ (app.testcenter.kz) на зимнее комплексное тестирование для поступления в научно-педагогическую и профильную магистратуру SDU University.",
                "passed_advice": "Регистрация на зимнее КТ завершена. Вы можете подготовиться и подать заявку на основной летний поток КТ (июнь–июль)."
            },
            "kk": {
                "title": "Магистратура (Қысқы қабылдау): Кешенді тестілеуге (КТ) тіркелу",
                "stage_name": "Магистратураның қысқы КТ-сына өтініш қабылдау",
                "description": "SDU университетінің ғылыми-педагогикалық және бейіндік магистратурасына түсу үшін ҰТО порталында (app.testcenter.kz) қысқы кешенді тестілеуге онлайн тіркелу.",
                "passed_advice": "Қысқы КТ-ға тіркелу аяқталды. Сіз негізгі жазғы КТ кезеңіне (маусым–шілде) дайындалып, құжат тапсыра аласыз."
            },
            "en": {
                "title": "Master's Degree (Winter Intake): Comprehensive Testing (CT) Registration",
                "stage_name": "Winter Graduate CT Application Window",
                "description": "Online registration via the National Testing Center (app.testcenter.kz) for Winter Comprehensive Testing required for SDU Master's programs.",
                "passed_advice": "Winter CT registration is closed. You may apply for the main Summer Comprehensive Testing session in June–July."
            }
        }
    },
    {
        "id": "sdu_master_winter_docs",
        "date_start": "2026-11-15",
        "date_end": "2026-12-20",
        "category": "contract",
        "degree_level": "graduate",
        "action_url": "https://sdu.edu.kz/admission",
        "i18n": {
            "ru": {
                "title": "SDU Магистратура (Зимний прием): Подача заявок и документов",
                "stage_name": "Прием документов на весенний семестр магистратуры SDU",
                "description": "Подача онлайн-заявки (до 30 ноября) и предоставление оригиналов документов (диплом бакалавра, сертификат КТ / IELTS от 6.0) в приемную комиссию SDU до 20 декабря.",
                "passed_advice": "Зимний прием документов в магистратуру SDU завершен. Основной летний прием открывается 20 июня."
            },
            "kk": {
                "title": "SDU Магистратура (Қысқы қабылдау): Өтініштер мен құжаттарды қабылдау",
                "stage_name": "SDU магистратурасының көктемгі семестріне құжат қабылдау",
                "description": "Онлайн өтініш беру (30 қарашаға дейін) және құжаттардың түпнұсқасын (бакалавр дипломы, КТ сертификаты / IELTS 6.0+) 20 желтоқсанға дейін SDU қабылдау комиссиясына тапсыру.",
                "passed_advice": "SDU магистратурасына қысқы құжат қабылдау аяқталды. Негізгі жазғы қабылдау 20 маусымда басталады."
            },
            "en": {
                "title": "SDU Master's Degree (Winter Intake): Application & Document Submission",
                "stage_name": "Spring Semester Graduate Admissions & Document Filing",
                "description": "Submit your online application (by Nov 30) and original documents (Bachelor's diploma, CT certificate, IELTS 6.0+ / TOEFL iBT 60+) to SDU Admissions by December 20.",
                "passed_advice": "Winter graduate document submission is closed. The main summer intake opens on June 20."
            }
        }
    },
    {
        "id": "grad_winter_kt_exam",
        "date_start": "2026-11-18",
        "date_end": "2026-12-11",
        "category": "exam",
        "degree_level": "graduate",
        "action_url": "https://testcenter.kz",
        "i18n": {
            "ru": {
                "title": "Магистратура (Зимний поток): Проведение Комплексного тестирования (КТ)",
                "stage_name": "Сдача зимнего КТ для поступающих в магистратуру",
                "description": "Сдача КТ (иностранный язык, ТГО, профильные дисциплины). Проходной балл в SDU: от 75 баллов (научно-педагогическая) и от 50 баллов (профильная магистратура).",
                "passed_advice": "Зимнее тестирование КТ завершено. Следующая сессия КТ для магистратуры состоится в июле–августе."
            },
            "kk": {
                "title": "Магистратура (Қысқы қабылдау): Кешенді тестілеуді (КТ) өткізу",
                "stage_name": "Магистратураға түсушілер үшін қысқы КТ тапсыру",
                "description": "Кешенді тестілеуді тапсыру (шет тілі, ОДТ, бейіндік пәндер). SDU шекті балы: ғылыми-педагогикалық бағыт — кемінде 75 балл, бейіндік бағыт — кемінде 50 балл.",
                "passed_advice": "Қысқы КТ тестілеуі аяқталды. Магистратураға арналған келесі КТ сессиясы шілде–тамыз айларында өтеді."
            },
            "en": {
                "title": "Master's Degree (Winter Intake): Comprehensive Testing (CT) Exam Period",
                "stage_name": "Winter Graduate CT Examination Window",
                "description": "Comprehensive Testing period (Foreign Language, Readiness Test, Major Subjects). SDU minimum threshold: 75 points (Research track) or 50 points (Profile track).",
                "passed_advice": "Winter CT examinations have concluded. The next graduate testing window takes place in July–August."
            }
        }
    },
    {
        "id": "grad_winter_grant_enrollment",
        "date_start": "2026-12-12",
        "date_end": "2027-01-10",
        "category": "grant",
        "degree_level": "graduate",
        "action_url": "https://app.sdu.edu.kz",
        "i18n": {
            "ru": {
                "title": "Магистратура (Зимний набор): Конкурс грантов и зачисление в SDU",
                "stage_name": "Зимний конкурс грантов РК и зачисление магистрантов",
                "description": "Подача заявлений на зимний конкурс государственных образовательных грантов (12–18 декабря) и финальное зачисление в магистратуру SDU University (до 10 января, старт семестра — середина января).",
                "passed_advice": "Зимнее зачисление в магистратуру завершено. Вы можете подать документы на летний конкурс грантов в июле."
            },
            "kk": {
                "title": "Магистратура (Қысқы қабылдау): Грант байқауы және SDU-ға қабылдау",
                "stage_name": "ҚР қысқы грант байқауы және магистранттарды қабылдау",
                "description": "Мемлекеттік білім беру гранттарының қысқы байқауына өтініш беру (12–18 желтоқсан) және SDU магистратурасына қабылдау (10 қаңтарға дейін, оқудың басталуы — қаңтардың ортасы).",
                "passed_advice": "Магистратураға қысқы қабылдау аяқталды. Шілде айындағы жазғы грант байқауына құжат тапсыра аласыз."
            },
            "en": {
                "title": "Master's Degree (Winter Intake): State Grant Competition & SDU Enrollment",
                "stage_name": "Winter Graduate Grant Applications & Final Enrollment",
                "description": "State grant competition filing (Dec 12–18) and final enrollment for SDU Master's programs (through Jan 10; Spring semester classes begin in mid-January).",
                "passed_advice": "Winter graduate enrollment is closed. Applications for the main summer grant competition open in July."
            }
        }
    },
    {
        "id": "unt_january_2027",
        "date_start": "2026-12-20",
        "date_end": "2027-02-10",
        "category": "unt",
        "degree_level": "undergraduate",
        "action_url": "https://app.testcenter.kz",
        "i18n": {
            "ru": {
                "title": "ЕНТ-2027: Регистрация и проведение Январского ЕНТ (Бакалавриат)",
                "stage_name": "Онлайн-регистрация (с 20 декабря) и сдача январского ЕНТ",
                "description": "Прием заявлений (20–30 декабря на app.testcenter.kz) и проведение январского тестирования ЕНТ (10 января – 10 февраля 2027) для поступления на платное отделение SDU University.",
                "passed_advice": "Январское ЕНТ завершено. Зарегистрируйтесь на мартовское или основное (май–июль) тестирование ЕНТ."
            },
            "kk": {
                "title": "ҰБТ-2027: Қаңтардағы ҰБТ-ға тіркелу және тапсыру (Бакалавриат)",
                "stage_name": "Онлайн тіркелу (20 желтоқсаннан) және қаңтар ҰБТ-сын тапсыру",
                "description": "SDU университетінің ақылы бөліміне түсу үшін өтініш қабылдау (20–30 желтоқсан app.testcenter.kz) және қаңтар айындағы ҰБТ тестілеуін өткізу (10 қаңтар – 10 ақпан 2027).",
                "passed_advice": "Қаңтар ҰБТ-сы аяқталды. Наурыз немесе негізгі (мамыр–шілде) ҰБТ тестілеуіне тіркеліңіз."
            },
            "en": {
                "title": "UNT-2027: January UNT Registration & Testing Session (Undergraduate)",
                "stage_name": "Online Registration (from Dec 20) & January UNT Testing",
                "description": "Registration window (Dec 20–30 via app.testcenter.kz) and January UNT testing session (Jan 10 – Feb 10, 2027) for fee-paying undergraduate admission at SDU University.",
                "passed_advice": "January UNT session has concluded. Register for the March or Main (May–July) UNT sessions."
            }
        }
    },
    {
        "id": "spt_olympiad_2027",
        "date_start": "2027-01-15",
        "date_end": "2027-03-10",
        "category": "olympiad",
        "degree_level": "undergraduate",
        "action_url": "https://sdu.edu.kz/spt",
        "i18n": {
            "ru": {
                "title": "Олимпиада SDU SPT 2027: Внутренние гранты и скидки до 100%",
                "stage_name": "Регистрация, I этап (онлайн) и II этап (офлайн) олимпиады SPT",
                "description": "Ежегодная республиканская олимпиада SDU Proficiency Test для выпускников школ и колледжей. Регистрация до середины февраля, I онлайн-тур (50 логических вопросов) в феврале и II офлайн-тур (100 вопросов по кластерам) в начале марта. Разыгрываются 100%, 50% и 30% гранты/скидки SDU на 4 года.",
                "passed_advice": "Олимпиада SPT 2027 завершена. Вы можете участвовать в конкурсе государственных грантов РК или получить скидку SDU за высокие баллы ЕНТ."
            },
            "kk": {
                "title": "SDU SPT 2027 Олимпиадасы: Ішкі гранттар және 100%-ға дейін жеңілдіктер",
                "stage_name": "SPT олимпиадасына тіркелу, I кезең (онлайн) және II кезең (офлайн)",
                "description": "Мектеп және колледж бітірушілеріне арналған республикалық SDU Proficiency Test олимпиадасы. Ақпан ортасына дейін тіркелу, ақпанда I онлайн кезең (50 логикалық сұрақ) және наурыз басында II офлайн кезең (кластер бойынша 100 сұрақ). Жеңімпаздарға 4 жылға 100%, 50%, 30% SDU гранттары мен жеңілдіктері беріледі.",
                "passed_advice": "SPT 2027 олимпиадасы аяқталды. Сіз ҚР мемлекеттік грант конкурсына немесе жоғары ҰБТ балдары үшін берілетін жеңілдіктерге өтініш бере аласыз."
            },
            "en": {
                "title": "SDU SPT Olympiad 2027: Internal Grants & Up to 100% Scholarships",
                "stage_name": "SPT Registration, Stage I (Online) & Stage II (Offline Finals)",
                "description": "Annual SDU Proficiency Test for high school and college seniors. Registration runs until mid-February; Stage I (50 online logic questions) in February and Stage II (100 offline subject cluster questions across Kazakhstan) in early March. Awards 4-year 100%, 50%, and 30% tuition scholarships.",
                "passed_advice": "SPT 2027 has concluded. You may compete for Republic of Kazakhstan state grants or SDU merit scholarships via UNT scores."
            }
        }
    },
    {
        "id": "unt_march_2027",
        "date_start": "2027-02-15",
        "date_end": "2027-03-31",
        "category": "unt",
        "degree_level": "undergraduate",
        "action_url": "https://app.testcenter.kz",
        "i18n": {
            "ru": {
                "title": "ЕНТ-2027: Регистрация и сдача Мартовского ЕНТ (Бакалавриат)",
                "stage_name": "Весенняя сессия ЕНТ для поступления на платное отделение",
                "description": "Регистрация (с середины февраля на app.testcenter.kz) и проведение мартовского ЕНТ (март 2027) для абитуриентов бакалавриата SDU University.",
                "passed_advice": "Мартовское ЕНТ завершено. Зарегистрируйтесь на основное ЕНТ (май–июль) для участия в конкурсе государственных грантов."
            },
            "kk": {
                "title": "ҰБТ-2027: Наурыздағы ҰБТ-ға тіркелу және тапсыру (Бакалавриат)",
                "stage_name": "Ақылы бөлімге түсуге арналған көктемгі ҰБТ сессиясы",
                "description": "SDU университетінің бакалавриат талапкерлері үшін наурыз айындағы ҰБТ-ға тіркелу (ақпан ортасынан app.testcenter.kz) және тестілеуден өту (наурыз 2027).",
                "passed_advice": "Наурыз ҰБТ-сы аяқталды. Мемлекеттік грант конкурсына қатысу үшін негізгі ҰБТ-ға (мамыр–шілде) тіркеліңіз."
            },
            "en": {
                "title": "UNT-2027: March UNT Registration & Testing Session (Undergraduate)",
                "stage_name": "Spring UNT Session for Fee-Paying Admission",
                "description": "Online registration (starting mid-February via app.testcenter.kz) and March UNT testing window (March 2027) for prospective SDU undergraduate students.",
                "passed_advice": "March UNT testing is closed. Register for the Main UNT session (May–July) to compete for state educational grants."
            }
        }
    }
]


def _parse_date(d_val) -> date:
    if isinstance(d_val, date):
        return d_val
    return datetime.strptime(str(d_val), "%Y-%m-%d").date()


def compute_status_and_days_left(date_start: date, date_end: date, ref_date: date) -> Tuple[str, int]:
    """Computes status (active, upcoming, passed) and days remaining relative to ref_date."""
    if ref_date > date_end:
        return "passed", 0
    elif ref_date >= date_start:
        return "active", max(0, (date_end - ref_date).days)
    else:
        # upcoming stage: days left until stage deadline closes (or until it starts)
        return "upcoming", max(0, (date_end - ref_date).days)


def get_all_deadlines(
    category: Optional[str] = None,
    degree_level: Optional[str] = None,
    lang: str = "ru",
    reference_date: Optional[date] = None,
    status: Optional[str] = None,
) -> List[Dict]:
    """Returns official admissions campaign deadlines with localized text and dynamic statuses."""
    ref_date = reference_date or local_today()
    if isinstance(ref_date, str):
        ref_date = _parse_date(ref_date)

    lang_key = lang.lower() if lang else "ru"
    if lang_key not in ("ru", "kk", "en"):
        lang_key = "ru"

    status_filter = status.lower().strip() if status else None

    results = []
    for item in OFFICIAL_DEADLINES:
        # Filter by category
        if category and item["category"].lower() != category.lower():
            continue

        # Filter by degree_level ('all' matches both undergraduate and graduate)
        if degree_level and degree_level.lower() != "all":
            if item["degree_level"] != "all" and item["degree_level"].lower() != degree_level.lower():
                continue

        d_start = _parse_date(item["date_start"])
        d_end = _parse_date(item["date_end"])
        item_status, days_left = compute_status_and_days_left(d_start, d_end, ref_date)

        if status_filter and status_filter != "all":
            if status_filter == "upcoming_active":
                if item_status not in ("active", "upcoming"):
                    continue
            elif item_status != status_filter:
                continue

        texts = item["i18n"].get(lang_key) or item["i18n"]["ru"]

        results.append({
            "id": item["id"],
            "title": texts["title"],
            "stage_name": texts["stage_name"],
            "date_start": item["date_start"],
            "date_end": item["date_end"],
            "category": item["category"],
            "degree_level": item["degree_level"],
            "status": item_status,
            "days_left": days_left,
            "description": texts["description"],
            "action_url": item["action_url"],
            "passed_advice": texts.get("passed_advice"),
        })

    # Sort active and upcoming milestones first (chronologically), followed by concluded milestones
    status_priority = {"active": 0, "upcoming": 1, "passed": 2}
    results.sort(key=lambda x: (status_priority.get(x["status"], 3), x["date_start"], x["date_end"]))
    return results


def get_upcoming_deadlines_for_alert(
    days_ahead: int,
    reference_date: Optional[date] = None,
    lang: str = "ru",
) -> List[Dict]:
    """Returns deadlines occurring exactly in days_ahead days (closing or opening)."""
    ref_date = reference_date or local_today()
    if isinstance(ref_date, str):
        ref_date = _parse_date(ref_date)

    all_items = get_all_deadlines(lang=lang, reference_date=ref_date)
    matching = []

    for item in all_items:
        d_start = _parse_date(item["date_start"])
        d_end = _parse_date(item["date_end"])

        # Check closing deadline (e.g. 3 days before end)
        days_to_end = (d_end - ref_date).days
        # Check opening start date (e.g. 3 days before start)
        days_to_start = (d_start - ref_date).days

        if days_to_end == days_ahead or days_to_start == days_ahead:
            alert_type = "closing" if days_to_end == days_ahead else "opening"
            item_copy = dict(item)
            item_copy["alert_type"] = alert_type
            item_copy["alert_days_ahead"] = days_ahead
            matching.append(item_copy)

    return matching


def get_calendar_events(
    year: int = 2026,
    month: Optional[int] = None,
    lang: str = "ru",
    reference_date: Optional[date] = None,
) -> Dict:
    """Returns calendar grid representation grouped by month where each day has an array of deadline events."""
    ref_date = reference_date or local_today()
    if isinstance(ref_date, str):
        ref_date = _parse_date(ref_date)

    all_items = get_all_deadlines(lang=lang, reference_date=ref_date)

    # Determine months to include
    if month is not None:
        target_months = [month]
    else:
        # All months in the campaign (Jan to Aug) or 1..12
        target_months = list(range(1, 13))

    month_names = {
        "ru": ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"],
        "kk": ["", "Қаңтар", "Ақпан", "Наурыз", "Сәуір", "Мамыр", "Маусым", "Шілде", "Тамыз", "Қыркүйек", "Қазан", "Қараша", "Желтоқсан"],
        "en": ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    }
    lang_key = lang.lower() if lang in ("ru", "kk", "en") else "ru"

    months_output = []
    total_events_count = 0

    for m in target_months:
        _, num_days = calendar.monthrange(year, m)
        m_start = date(year, m, 1)
        m_end = date(year, m, num_days)

        month_events = []
        days_map: Dict[int, List[Dict]] = {d: [] for d in range(1, num_days + 1)}

        for item in all_items:
            ev_start = _parse_date(item["date_start"])
            ev_end = _parse_date(item["date_end"])

            # Check if event overlaps with month [m_start, m_end]
            if ev_start <= m_end and ev_end >= m_start:
                color = CATEGORY_COLORS.get(item["category"], "blue")
                ev_data = {
                    "id": item["id"],
                    "title": item["title"],
                    "stage_name": item["stage_name"],
                    "category": item["category"],
                    "color": color,
                    "date_start": item["date_start"],
                    "date_end": item["date_end"],
                    "status": item["status"],
                    "action_url": item["action_url"],
                }
                month_events.append(ev_data)
                total_events_count += 1

                # Populate days_map for active days in this month
                day_start_num = max(1, (ev_start - m_start).days + 1) if ev_start.year == year and ev_start.month == m else 1
                day_end_num = min(num_days, (ev_end - m_start).days + 1) if ev_end.year == year and ev_end.month == m else num_days

                for day_idx in range(day_start_num, day_end_num + 1):
                    days_map[day_idx].append({
                        "id": item["id"],
                        "title": item["title"],
                        "category": item["category"],
                        "color": color,
                        "status": item["status"],
                        "action_url": item["action_url"],
                    })

        months_output.append({
            "year": year,
            "month": m,
            "month_name": month_names[lang_key][m],
            "events": month_events,
            "days": days_map,
        })

    return {
        "year": year,
        "total_events": total_events_count,
        "months": months_output,
    }
