from django.contrib import admin
from django.utils.html import format_html
from .models import GradeLevel, Student, Finance, AcademicCalendar, Discipline


# =============================================================
# GRADE LEVEL ADMIN
# =============================================================

@admin.register(GradeLevel)
class GradeLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'formatted_tuition', 'description', 'order', 'student_count')
    list_editable = ['order']
    search_fields = ['name']
    ordering = ['order', 'name']

    def formatted_tuition(self, obj):
        """
        Safe and clean formatting for tuition fee.
        No SafeString issues, no float conversion errors.
        """
        try:
            value = obj.tuition_fee or 0
            value = float(value)

            return format_html(
                '<strong style="color:#198754;">L${:,.2f}</strong>',
                value
            )
        except Exception:
            return "L$0.00"

    formatted_tuition.short_description = "Tuition Fee"

    def student_count(self, obj):
        count = obj.students.filter(is_active=True).count()
        return format_html(
            '<span style="background:#e8f4f8;padding:2px 8px;border-radius:10px;">'
            '{} student{}</span>',
            count, 's' if count != 1 else ''
        )

    student_count.short_description = "Active Students"


# =============================================================
# STUDENT ADMIN
# =============================================================

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        'student_name', 'gender', 'grade_level',
        'is_active', 'date_enrolled', 'finance_status'
    ]
    list_filter = ['is_active', 'grade_level', 'gender']
    search_fields = ['student_name']
    list_editable = ['is_active']

    fieldsets = (
        ('Personal Information', {
            'fields': ('student_name', 'gender')
        }),
        ('Enrollment', {
            'fields': ('grade_level', 'is_active'),
            'description': (
                '⚠️ Selecting a Grade Level will automatically manage '
                'the student Finance record.'
            )
        }),
    )

    def finance_status(self, obj):
        try:
            status = obj.finance.payment_status

            colors = {
                'fully_paid': ('#d1fae5', '#065f46', 'Fully Paid'),
                'partial': ('#fef3c7', '#92400e', 'Partial'),
                'unpaid': ('#fee2e2', '#991b1b', 'Unpaid'),
            }

            bg, color, label = colors.get(
                status, ('#f3f4f6', '#374151', status)
            )

            return format_html(
                '<span style="background:{};color:{};padding:2px 10px;'
                'border-radius:10px;font-size:0.78em;">{}</span>',
                bg, color, label
            )
        except Exception:
            return format_html('<span style="color:#9ca3af;">No record</span>')

    finance_status.short_description = "Fee Status"


# =============================================================
# FINANCE ADMIN
# =============================================================

@admin.register(Finance)
class FinanceAdmin(admin.ModelAdmin):
    list_display = [
        'student', 'grade_level_name', 'formatted_due',
        'formatted_paid', 'formatted_balance',
        'payment_status', 'last_payment_date'
    ]

    list_filter = ['payment_status', 'student__grade_level']
    search_fields = ['student__student_name']

    readonly_fields = ['total_fees_due', 'payment_status', 'balance_display']

    fieldsets = (
        ('Student', {
            'fields': ('student',)
        }),
        ('Fee Information (auto-managed)', {
            'fields': ('total_fees_due', 'payment_status', 'balance_display'),
            'description': '🔒 Automatically calculated from Grade Level.'
        }),
        ('Payment Entry', {
            'fields': ('amount_paid', 'last_payment_date')
        }),
    )

    def grade_level_name(self, obj):
        return obj.student.grade_level.name

    grade_level_name.short_description = "Grade"

    def formatted_due(self, obj):
        try:
            return f"L${float(obj.total_fees_due):,.2f}"
        except Exception:
            return "L$0.00"

    formatted_due.short_description = "Fees Due"

    def formatted_paid(self, obj):
        color = '#065f46' if obj.amount_paid >= obj.total_fees_due else '#92400e'
        amount = f'{float(obj.amount_paid):,.2f}'
        return format_html(
            '<strong style="color:{};">L${}</strong>',
            color, amount
        )

    formatted_paid.short_description = "Amount Paid"

    # ✅ FIXED: NOW INSIDE CLASS
    def formatted_balance(self, obj):
        try:
            bal = float(obj.balance())
            color = '#065f46' if bal == 0 else '#991b1b'

            return format_html(
                '<span style="color:{};">L${:,.2f}</span>',
                color, bal
            )
        except Exception:
            return "L$0.00"

    formatted_balance.short_description = "Balance"

    # ✅ FIXED: NOW INSIDE CLASS
    def balance_display(self, obj):
        try:
            bal = float(obj.balance())
            return format_html(
                '<strong style="font-size:1.1em;color:{};">L${:,.2f}</strong>',
                '#065f46' if bal == 0 else '#dc2626',
                bal
            )
        except Exception:
            return "L$0.00"

    balance_display.short_description = "Outstanding Balance"


# =============================================================
# DISCIPLINE ADMIN
# =============================================================

@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display = ['student', 'action_taken', 'date', 'issued_by']
    list_filter = ['action_taken', 'date']
    search_fields = ['student__student_name', 'reason']
    
