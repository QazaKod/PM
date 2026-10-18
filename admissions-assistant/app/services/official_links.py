"""US9: Official Source Links Service.

Provides verified, official digital resources for SDU Admissions,
including portals, testing center, state grant application, internal olympiad,
contact channels, and dormitory info.
"""
from typing import Dict, List, Any

OFFICIAL_LINKS_DATA: List[Dict[str, Any]] = [
    {
        "id": "sdu_portal",
        "title": "Portal SDU",
        "name_ru": "Официальный портал SDU",
        "url": "https://sdu.edu.kz",
        "category": "portal",
        "description": "Главный официальный веб-сайт SDU University (новости, структура, академия)."
    },
    {
        "id": "admissions_portal",
        "title": "Admissions Office Portal",
        "name_ru": "Портал приемной комиссии SDU",
        "url": "https://admissions.sdu.edu.kz",
        "category": "portal",
        "description": "Личный кабинет абитуриента, онлайн-подача документов, отслеживание статуса заявления."
    },
    {
        "id": "testcenter",
        "title": "National Testing Center (ЕНТ)",
        "name_ru": "Национальный центр тестирования (НЦТ / ЕНТ)",
        "url": "https://testcenter.kz",
        "category": "testing",
        "description": "Официальный сайт НЦТ МНВО РК: регистрация на ЕНТ и КТ, сертификаты с QR, апелляции."
    },
    {
        "id": "egov",
        "title": "eGov (Госгранты)",
        "name_ru": "Электронное правительство eGov (Госгранты РК)",
        "url": "https://egov.kz",
        "category": "grants",
        "description": "Подача заявления на участие в республиканском конкурсе государственных образовательных грантов."
    },
    {
        "id": "sdu_spt",
        "title": "SDU SPT Olympiad",
        "name_ru": "Олимпиада SDU SPT (SDU Proficiency Test)",
        "url": "https://spt.sdu.edu.kz",
        "category": "grants",
        "description": "Республиканская олимпиада для школьников и выпускников колледжей с фондом внутренних 100% грантов и скидок."
    },
    {
        "id": "whatsapp_admissions",
        "title": "WhatsApp Admissions Office",
        "name_ru": "WhatsApp приемной комиссии SDU",
        "url": "https://wa.me/77020001133",
        "category": "contacts",
        "description": "Официальный канал оперативной консультации абитуриентов приемной комиссией в мессенджере WhatsApp."
    },
    {
        "id": "telegram_bot",
        "title": "Telegram Bot",
        "name_ru": "SDU Admissions Telegram Bot",
        "url": "https://t.me/sdu_admissions_registration_bot",
        "category": "contacts",
        "description": "Официальный чат-бот для регистрации, верификации телефонных номеров и консультаций."
    },
    {
        "id": "dormitory",
        "title": "Student Dormitory Info",
        "name_ru": "Студенческие общежития SDU",
        "url": "https://sdu.edu.kz/dormitory",
        "category": "campus",
        "description": "Информация о комнатах, правилах проживания, стоимости и онлайн-подаче заявки на общежитие."
    }
]


def get_official_links() -> Dict[str, Any]:
    """Retrieve verified official SDU links directory.

    Returns:
        Dict with list of link objects and dictionary keyed by link id.
    """
    links_by_id = {item["id"]: item["url"] for item in OFFICIAL_LINKS_DATA}
    return {
        "verified": True,
        "total": len(OFFICIAL_LINKS_DATA),
        "links": OFFICIAL_LINKS_DATA,
        "urls": links_by_id,
    }
