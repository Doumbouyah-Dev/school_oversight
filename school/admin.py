# school/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import (
    GradeLevel,
    Student,
    Finance,
    PaymentTransaction,
    AcademicCalendar,
    Discipline,
)


# =============================================================
# GRADE LEVEL ADMIN
# Set up grades here FIRST before adding any students.
# =============================================================

@admin.register(GradeLevel)
class GradeLevelAdmin(admin.ModelAdmin):
    list_display  = ['name', 'formatted_tuition', 'description', 'order', 'student_count']
    list_editable = ['order']
    search_fields = ['name']
    ordering      = ['order', 'name']

    def formatted_tuition(self, obj):
        amount = '{:,.2f}'.format(float(obj.tuition_fee))
        return format_html('<strong style="color:#198754;">L${}</strong>', amount)
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
    list_display  = [
        'student_name', 'gender', 'grade_level',
        'is_active', 'date_enrolled', 'finance_status'
    ]
    list_filter   = ['is_active', 'grade_level', 'gender']
    search_fields = ['student_name']
    list_editable = ['is_active']

    fieldsets = (
        ('Personal Information', {
            'fields': ('student_name', 'gender')
        }),
        ('Enrollment', {
            'fields': ('grade_level', 'is_active'),
            'description': (
                'Selecting a Grade Level will automatically create or update '
                "the student's Finance record with the correct tuition fee."
            )
        }),
    )

    def finance_status(self, obj):
        try:
            status = obj.finance.payment_status
            colors = {
                'fully_paid': ('#d1fae5', '#065f46', 'Fully Paid'),
                'partial':    ('#fef3c7', '#92400e', 'Partial'),
                'unpaid':     ('#fee2e2', '#991b1b', 'Unpaid'),
            }
            bg, color, label = colors.get(status, ('#f3f4f6', '#374151', status))
            return format_html(
                '<span style="background:{};color:{};padding:2px 10px;'
                'border-radius:10px;font-size:.78em;">{}</span>',
                bg, color, label
            )
        except Exception:
            return format_html('<span style="color:#9ca3af;">No record</span>')
    finance_status.short_description = "Fee Status"


# =============================================================
# PAYMENT TRANSACTION INLINE
# Defined BEFORE FinanceAdmin so it can be referenced inside it.
# =============================================================

class PaymentTransactionInline(admin.TabularInline):
    """
    Shows all payment transactions directly inside the Finance
    edit page — the Bursar sees the full payment history without
    navigating away, and adds new payments from the same page.
    """
    model           = PaymentTransaction
    extra           = 1
    readonly_fields = ['receipt_number', 'created_at']
    fields          = [
        'receipt_number', 'amount', 'date',
        'received_by', 'payment_method', 'notes'
    ]

    def get_readonly_fields(self, request, obj=None):
        return ['receipt_number', 'created_at']


# =============================================================
# FINANCE ADMIN
# Comes AFTER PaymentTransactionInline — order matters.
# =============================================================

@admin.register(Finance)
class FinanceAdmin(admin.ModelAdmin):
    list_display  = [
        'student', 'grade_level_name', 'formatted_due',
        'formatted_paid', 'formatted_balance',
        'payment_status', 'transaction_count', 'last_payment_date'
    ]
    list_filter   = ['payment_status', 'student__grade_level']
    search_fields = ['student__student_name']

    # These fields are auto-managed — staff must not edit them directly
    readonly_fields = [
        'total_fees_due', 'payment_status',
        'amount_paid', 'balance_display'
    ]

    # PaymentTransactionInline is now defined above — no NameError
    inlines = [PaymentTransactionInline]

    fieldsets = (
        ('Student', {
            'fields': ('student',)
        }),
        ('Fee Summary (read-only — updated automatically)', {
            'fields': ('total_fees_due', 'amount_paid', 'payment_status', 'balance_display'),
            'description': (
                'These fields are calculated automatically from payment '
                'transactions below. Add a new transaction row to record a payment.'
            )
        }),
        ('Last Payment', {
            'fields': ('last_payment_date',),
        }),
    )

    def grade_level_name(self, obj):
        return obj.student.grade_level.name
    grade_level_name.short_description = "Grade"

    def formatted_due(self, obj):
        amount = '{:,.2f}'.format(float(obj.total_fees_due))
        return format_html('L${}', amount)
    formatted_due.short_description = "Fees Due"

    def formatted_paid(self, obj):
        amount = '{:,.2f}'.format(float(obj.amount_paid))
        color  = '#065f46' if obj.amount_paid >= obj.total_fees_due else '#92400e'
        return format_html('<strong style="color:{};">L${}</strong>', color, amount)
    formatted_paid.short_description = "Amount Paid"

    def formatted_balance(self, obj):
        bal    = float(obj.balance())
        amount = '{:,.2f}'.format(bal)
        color  = '#065f46' if bal == 0 else '#991b1b'
        return format_html('<span style="color:{};">L${}</span>', color, amount)
    formatted_balance.short_description = "Balance"

    def balance_display(self, obj):
        bal    = float(obj.balance())
        amount = '{:,.2f}'.format(bal)
        return format_html(
            '<strong style="font-size:1.1em;color:{};">L${}</strong>',
            '#065f46' if bal == 0 else '#dc2626', amount
        )
    balance_display.short_description = "Outstanding Balance"
    
    def transaction_count(self, obj):
        count = obj.transactions.count()
        return format_html(
            '<span style="background:#eff4ff;color:#1d4ed8;padding:2px 8px;'
            'border-radius:10px;font-size:.78em;">{} payment{}</span>',
            count, 's' if count != 1 else ''
        )
    transaction_count.short_description = "Payments"

    def balance_display(self, obj):
        if not obj.pk:
            return '—'
        bal    = float(obj.balance())
        amount = '{:,.2f}'.format(bal)
        return format_html(
            '<strong style="font-size:1.1em;color:{};">L${}</strong>',
            '#065f46' if bal == 0 else '#dc2626', amount
        )
    balance_display.short_description = "Outstanding Balance"
# =============================================================
# PAYMENT TRANSACTION ADMIN (standalone — full list view)
# =============================================================

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display    = [
        'receipt_number', 'student_name', 'amount_display',
        'payment_method', 'date', 'received_by'
    ]
    list_filter     = ['payment_method', 'date', 'received_by']
    search_fields   = [
        'receipt_number',
        'finance__student__student_name',
        'received_by'
    ]
    readonly_fields = ['receipt_number', 'created_at']
    date_hierarchy  = 'date'

    fieldsets = (
        ('Receipt', {
            'fields': ('receipt_number', 'created_at')
        }),
        ('Payment Details', {
            'fields': ('finance', 'amount', 'date', 'payment_method')
        }),
        ('Collected By', {
            'fields': ('received_by', 'notes')
        }),
    )

    def student_name(self, obj):
        return obj.finance.student.student_name
    student_name.short_description = "Student"
    student_name.admin_order_field = 'finance__student__student_name'

    def amount_display(self, obj):
        amount = '{:,.2f}'.format(float(obj.amount))
        return format_html('<strong style="color:#065f46;">L${}</strong>', amount)
    amount_display.short_description = "Amount"
    amount_display.admin_order_field = 'amount'

# =============================================================
# ACADEMIC CALENDAR ADMIN
# =============================================================

@admin.register(AcademicCalendar)
class AcademicCalendarAdmin(admin.ModelAdmin):
    list_display  = ['event_name', 'event_type', 'start_date', 'end_date', 'status']
    list_filter   = ['event_type', 'status']
    search_fields = ['event_name']
    fieldsets = (
        ('Event Details', {
            'fields': ('event_name', 'event_type', 'description')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date', 'status')
        }),
    )


# =============================================================
# DISCIPLINE ADMIN
# =============================================================

@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display  = ['student', 'action_taken', 'date', 'issued_by']
    list_filter   = ['action_taken', 'date']
    search_fields = ['student__student_name', 'reason']
    


# =============================================================
# AUDIT LOG ADMIN
# A read-only log of all create/update/delete actions across the system,
# =============================================================


from .models import (
    GradeLevel, Student, Finance, PaymentTransaction,
    AcademicCalendar, Discipline, AuditLog
)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Read-only audit log in the admin.
    Nobody can add/edit/delete entries — it's a tamper-resistant record.
    """
    list_display  = [
        'timestamp_display', 'user', 'action_badge',
        'model_name', 'object_repr_short', 'description_short'
    ]
    list_filter   = ['action', 'model_name', 'user', 'timestamp']
    search_fields = ['description', 'object_repr', 'user__username']
    date_hierarchy = 'timestamp'
    readonly_fields = [
        'user', 'action', 'model_name', 'object_id',
        'object_repr', 'description', 'ip_address', 'timestamp'
    ]

    # Nobody can add/change/delete audit logs from the admin
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete old audit records
        return request.user.is_superuser

    def timestamp_display(self, obj):
        return format_html(
            '<span style="font-size:.8rem;color:#6c757d;font-family:monospace;">'
            '{}</span>',
            obj.timestamp.strftime('%b %d, %Y %H:%M')
        )
    timestamp_display.short_description = "When"
    timestamp_display.admin_order_field = 'timestamp'

    def action_badge(self, obj):
        colors = {
            'create':  ('#dcfce7', '#166534'),
            'update':  ('#dbeafe', '#1d4ed8'),
            'delete':  ('#fee2e2', '#991b1b'),
            'payment': ('#f0fdf4', '#065f46'),
            'login':   ('#f3f4f6', '#374151'),
        }
        bg, color = colors.get(obj.action, ('#f3f4f6', '#374151'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:10px;font-size:.72em;font-weight:600;">'
            '{}</span>',
            bg, color, obj.get_action_display()
        )
    action_badge.short_description = "Action"

    def object_repr_short(self, obj):
        return (
            obj.object_repr[:40] + '…'
            if len(obj.object_repr) > 40
            else obj.object_repr
        )
    object_repr_short.short_description = "Record"

    def description_short(self, obj):
        return (
            obj.description[:80] + '…'
            if len(obj.description) > 80
            else obj.description
        )
    description_short.short_description = "Description"