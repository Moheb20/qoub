# فصل حالات التسجيل عن حالات الجلسة
registration_states = {}  # للحالات المتعلقة بعملية التسجيل (login)
session_states = {}       # لحالات الجلسة بعد التسجيل (اختيار الفصل، نوع الامتحان...) 

# حالة الإدخال للأدمن عند إرسال رسالة جماعية
admin_states = {}

# حفظ حالة الأدمن عند إضافة/تعديل/حذف القروبات
admin_group_states = {}

# حفظ حالة الأدمن عند إضافة/تعديل/حذف المواعيد
admin_deadline_states = {}

# حالات اختيار الفروع والأقسام
branch_selection_states = {}
department_selection_states = {}

# حالات إدارة الأرقام
add_number_states = {}
edit_contact_states = {}
delete_contact_states = {}

# حالة تخزين اختيار الكلية لكل مستخدم
study_plan_states = {}