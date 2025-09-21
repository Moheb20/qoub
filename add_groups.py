import psycopg2
import os
from database import get_conn  # استيراد دالة الاتصال من ملفك

def add_all_groups():
    """إضافة جميع القروبات إلى قاعدة البيانات"""
    
    groups_data = [
        # جامعة
        {"name": "استفسارات", "category": "جامعة", "link": "https://chat.whatsapp.com/GoCdx1lqaGM7BCWY4ZHTNP"},
        {"name": "اخبار الجامعة", "category": "جامعة", "link": "https://chat.whatsapp.com/ITfbauxdP0ZH1rZ8HbGuOZ"},
        {"name": "جميع الفروع", "category": "جامعة", "link": "https://chat.whatsapp.com/EN3ABY6iHz99vlPlseswEw"},
        {"name": "طلبة وطالبات الجامعة", "category": "جامعة", "link": "https://chat.whatsapp.com/GhNuS7eByrBLwhiAmUFCb8"},
        {"name": "انشطة وحلول", "category": "جامعة", "link": "https://chat.whatsapp.com/H8Rhme2CSABCqM98EOd8Kz"},
        {"name": "كلية العلوم التربوية", "category": "جامعة", "link": "https://chat.whatsapp.com/Hy8JkM11OvG5vcmxnDLzuB"},
        {"name": "كلية الزراعة", "category": "جامعة", "link": "https://chat.whatsapp.com/IxWar55rbzVB8F2yimbBNt"},
        {"name": "كلية الاعلام", "category": "جامعة", "link": "https://chat.whatsapp.com/ElZRc4Wkbp4Ernw3v2uDuC"},
        {"name": "مساعدة الطلبة", "category": "جامعة", "link": "https://chat.whatsapp.com/FKDmknayLxeJShA0NSoPHV"},

        # تخصصات
        {"name": "انظمة المعلومات الحاسوبية", "category": "تخصصات", "link": "https://chat.whatsapp.com/HxEmcT3gS4pGfd8xbRNpz9"},
        {"name": "استفسارات عامة (محاسبة)", "category": "تخصصات", "link": "https://chat.whatsapp.com/CFkr2ow7mTc4TGXxge1Bwb"},
        {"name": "التربية الخاصة", "category": "تخصصات", "link": "https://chat.whatsapp.com/D6odKzuaRBmL7JmA2dRWvX"},
        {"name": "التسويق الرقمي", "category": "تخصصات", "link": "https://chat.whatsapp.com/DKUhBngaiQ20qx6YvfMFwC"},
        {"name": "الارشاد والصحة النفسية", "category": "تخصصات", "link": "https://chat.whatsapp.com/Ciop39lF8rj4q3p1JLhO9y"},
        {"name": "القضاء والسياسة الشرعية", "category": "تخصصات", "link": "https://chat.whatsapp.com/GQHGLIPrzGpLNxu1fWF089"},
        {"name": "اللغة الانجليزية", "category": "تخصصات", "link": "https://chat.whatsapp.com/KcIv1C5lz6mCcbZpdNSCMR"},
        {"name": "العلاقات العامة والاعلان", "category": "تخصصات", "link": "https://chat.whatsapp.com/ElZRc4Wkbp4Ernw3v2uDuC"},
        {"name": "التغذية والتصنيع الغذائي", "category": "تخصصات", "link": "https://chat.whatsapp.com/CIMjVn2i6coBb4vAONO5fd"},

        # مواد
        {"name": "محاسبة 2", "category": "مواد", "link": "https://chat.whatsapp.com/HRYyVv2by3FChHE5EjOwbp"},
        {"name": "مبادئ اقتصاد", "category": "مواد", "link": "https://chat.whatsapp.com/LfbHXpOUOz9A29n2XYzPEM"},
        {"name": "مبادئ الاحصاء", "category": "مواد", "link": "https://chat.whatsapp.com/Hg0BXz3qx7O8a6cqU7x7EN"},
        {"name": "علم النحو 1", "category": "مواد", "link": "https://chat.whatsapp.com/CjMv19fHiso51RTZ9MCIHX"},
        {"name": "مناهج البحث العلمي", "category": "مواد", "link": "https://chat.whatsapp.com/Ixv647y5WKB8IR43tTWpZc"},
        {"name": "المنهاج التربوي", "category": "مواد", "link": "https://chat.whatsapp.com/LN7NnmVHoIA7V9EWoAonmO"},
        {"name": "علم النفس التربوي", "category": "مواد", "link": "https://chat.whatsapp.com/BglsAZvRlrGH6rCyRLnAoR"},
        {"name": "القياس والتقويم", "category": "مواد", "link": "https://chat.whatsapp.com/LJfQxUk14BxH1ysxyZTUzK"},
        {"name": "تصميم التدريس", "category": "مواد", "link": "https://chat.whatsapp.com/BoHU1ifJd5n86dRTR1J3Zh"},
        {"name": "تكنولوجيا التعليم", "category": "مواد", "link": "https://chat.whatsapp.com/LZp2U5JdN4UCFzYrJKoObe"},
        {"name": "تفاضل وتكامل 1", "category": "مواد", "link": "https://chat.whatsapp.com/LqEI8ztvQLR4llrgCqZdee"},
        {"name": "الاحصاء التطبيقي", "category": "مواد", "link": "https://chat.whatsapp.com/CQDiRMD6p1X11MPMr60UwG"},
        {"name": "تعلم كيف تتعلم", "category": "مواد", "link": "https://chat.whatsapp.com/CeJa59mznTxDOHUIrYG2HP"},
        {"name": "الثقافة الاسلامية", "category": "مواد", "link": "https://chat.whatsapp.com/Ljz92I8RBeb6uFtdsbSpHK"},
        {"name": "تاريخ القدس", "category": "مواد", "link": "https://chat.whatsapp.com/B727rzlJ6fG8DQqSSBMkAg"},
        {"name": "مهارات حياتية", "category": "مواد", "link": "https://chat.whatsapp.com/EXSQLx3BuGJKPpjrpDoa53"},
        {"name": "فلسطين والقضية الفلسطينية", "category": "مواد", "link": "https://chat.whatsapp.com/DZs1DlkzmnJGIf1JlHlDYX"},
        {"name": "اللغة الانجليزية", "category": "مواد", "link": "https://chat.whatsapp.com/D1DOsObs2dGAAyoK0V5YaC"},
        {"name": "اللغة العربية 1", "category": "مواد", "link": "https://chat.whatsapp.com/FLfYRCNtebY3EPsiD7uGPp"},
        {"name": "مبادئ الحاسوب", "category": "مواد", "link": "https://chat.whatsapp.com/CPynN3OZm67InIvC3K1BZ4"},
        {"name": "الحركة الاسيرة", "category": "مواد", "link": "https://chat.whatsapp.com/E4j2B4ncNPN2bpT2S1ZFHJ"},
        {"name": "مكافحة الفساد", "category": "مواد", "link": "https://chat.whatsapp.com/IJOzzJyU7zQJo07wiybbLA"},
        {"name": "المسؤولية المجتمعية", "category": "مواد", "link": "https://chat.whatsapp.com/CrzU3XKsb1TCaakYZa27hA"},
        {"name": "اللغة العربية و ط ت", "category": "مواد", "link": "https://chat.whatsapp.com/LCArS1t4YMT6VUzvKGJ6Qi"},
        {"name": "الثقافة الاسلامية و ط ت", "category": "مواد", "link": "https://chat.whatsapp.com/Iw9X2cfBT8gFyc4HoXvv5t"},
        {"name": "الرياضيات و ط ت", "category": "مواد", "link": "https://chat.whatsapp.com/JeyUzLDdB1CCEYtVgjcrw9"},
        {"name": "رياضيات عامة", "category": "مواد", "link": "https://chat.whatsapp.com/KtEcLDbk4Xz0FkW6m3uM8U"},
        {"name": "العلوم والصحة و ط ت", "category": "مواد", "link": "https://chat.whatsapp.com/EIJ355pYlRF5cjnpYP1Z0T"},
        {"name": "العلوم الاجتماعية و ط ت", "category": "مواد", "link": "https://chat.whatsapp.com/LafDHmf0nnqGu5sBrf3ZYF"},
        {"name": "علم النفس التطوري", "category": "مواد", "link": "https://chat.whatsapp.com/Lppv3hq6CJZ6oqxs5mm1Bl"},
        {"name": "تعديل السلوك", "category": "مواد", "link": "https://chat.whatsapp.com/BwtqAdepHcpHFWQIt7drhb"},
        {"name": "الادب العربي وفنونه", "category": "مواد", "link": "https://chat.whatsapp.com/KUrUBLIhXndHtpfrSC7clM"},
        {"name": "التفكير الابداعي", "category": "مواد", "link": "https://chat.whatsapp.com/FkvU2389Qzu2vMwDFHrMs4"},
        {"name": "الموسيقى والاناشيد", "category": "مواد", "link": "https://chat.whatsapp.com/LYQH6H1ZFllKQCO0WWRruf"},
        {"name": "لغة عربية 2", "category": "مواد", "link": "https://chat.whatsapp.com/GD8o5QO12Tf7xoFKfoU9eF"},
        {"name": "قواعد الكتابة والترقيم", "category": "مواد", "link": "https://chat.whatsapp.com/IV0KQVlep5QJ1dBaRoqn5f"},
        {"name": "التربية الرياضية", "category": "مواد", "link": "https://chat.whatsapp.com/FRzFsB117xk0pUeg76NeLv"},
        {"name": "التربية الفنية و ط ت", "category": "مواد", "link": "https://chat.whatsapp.com/I0Vas9Z8X1pFkE9Ke8Ysvd"},
        {"name": "رعاية ذوي الاحتياجات الخاصة", "category": "مواد", "link": "https://chat.whatsapp.com/JNnm5GECVmIFgzTA8RY0Xw"},
        {"name": "الحاسوب في التعليم", "category": "مواد", "link": "https://chat.whatsapp.com/KlOtrGM8b93JcFekltBPBv"},
        {"name": "طرائق التدريس", "category": "مواد", "link": "https://chat.whatsapp.com/BvAJOUr8fp66VvEWDHXEFG"},
        {"name": "ادارة الصف وتنظيمه", "category": "مواد", "link": "https://chat.whatsapp.com/FDgewENfci54CutRyr4SEd"},
        {"name": "تربية عملية 1", "category": "مواد", "link": "https://chat.whatsapp.com/HgV95AU4xHtFsNqG3MbG1t"},
        {"name": "تربية عملية 2", "category": "مواد", "link": "https://chat.whatsapp.com/LS0xxaDp4NuI2rix8zUVtm"},
    ]

    added_count = 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            for group in groups_data:
                try:
                    cur.execute(
                        "INSERT INTO groups (category, name, link) VALUES (%s, %s, %s) ON CONFLICT (name) DO NOTHING",
                        (group["category"], group["name"], group["link"])
                    )
                    added_count += 1
                    print(f"تم إضافة: {group['name']}")
                except Exception as e:
                    print(f"خطأ في إضافة {group['name']}: {e}")
        conn.commit()
    
    print(f"تم إضافة {added_count} قروب بنجاح!")
    return added_count

if __name__ == "__main__":
    add_all_groups()
