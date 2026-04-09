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
    Discipline, Subject, 
    TermRecord, Result, AuditLog, TermFinance,
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
# RESULT INLINE — Defined BEFORE StudentAdmin so it can be referenced
# =============================================================

class ResultInline(admin.TabularInline):
    """
    Show all results for a student directly inside the
    Student admin page.
    """
    model         = Result
    extra         = 0
    readonly_fields = ['total_score', 'letter_grade', 'remark']
    fields        = [
        'subject', 'term_record',
        'ca_score', 'exam_score',
        'total_score', 'letter_grade', 'remark'
    ]


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
    inlines       = [ResultInline]

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

from django.contrib import admin
from django.utils.html import format_html

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    # 1. Organized display for quick evaluation
    list_display = [
        'student_name', 'grade_level', 'subject',
        'term_record', 'ca_score', 'exam_score',
        'total_score', 'grade_badge', 'remark_display'
    ]
    
    # 2. Filtering by Liberian academic standards
    list_filter = [
        'term_record',          # e.g., 1st Semester, 2nd Semester
        'student__grade_level', # e.g., Grade 9, Grade 12 (WASSCE class)
        'subject', 
        'letter_grade'
    ]
    
    search_fields = ['student__first_name', 'student__last_name', 'subject__name']
    readonly_fields = ['total_score', 'letter_grade', 'remark']

    fieldsets = (
        ('Student & Academic Cycle', {
            'fields': ('student', 'subject', 'term_record'),
            'description': 'Ensure the student is enrolled in the correct grade level for this period.'
        }),
        ('Score Entry (Liberian MoE Standards)', {
            'fields': (('ca_score', 'exam_score'),),
            'description': (
                'Standard weights: Continuous Assessment (CA) = 40% | '
                'Final Examination = 60%. Total = 100%.'
            )
        }),
        ('Computed Results', {
            'fields': (('total_score', 'letter_grade'), 'remark'),
            'classes': ('collapse',), # Clean up the UI
        }),
    )

    # Custom Badge for the Liberian Grading System
    def grade_badge(self, obj):
        colors = {
            'A': '#28a745', # Excellent (Green)
            'B': '#17a2b8', # Very Good (Cyan)
            'C': '#ffc107', # Good/Average (Yellow)
            'D': '#fd7e14', # Pass (Orange)
            'F': '#dc3545', # Fail (Red)
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 5px; font-weight: bold;">{}</span>',
            colors.get(obj.letter_grade, '#6c757d'),
            obj.letter_grade
        )
    grade_badge.short_description = 'Letter Grade'

    def remark_display(self, obj):
        if obj.total_score >= 70:
            return format_html('<b style="color: green;">Pass</b>')
        return format_html('<b style="color: red;">Fail</b>')
    remark_display.short_description = 'Status'

    def student_name(self, obj):
        return obj.student.student_name
    student_name.short_description = "Student"
    student_name.admin_order_field = 'student__student_name'

    def grade_level(self, obj):
        return obj.student.grade_level.name
    grade_level.short_description = "Grade"

    def grade_badge(self, obj):
        colors = {
            'A': ('#dcfce7', '#166534'),
            'B': ('#dbeafe', '#1d4ed8'),
            'C': ('#fef3c7', '#92400e'),
            'D': ('#fff7ed', '#9a3412'),
            'F': ('#fee2e2', '#991b1b'),
        }
        bg, color = colors.get(obj.letter_grade, ('#f3f4f6', '#374151'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;'
            'border-radius:10px;font-size:.8em;font-weight:700;">'
            '{}</span>',
            bg, color, obj.letter_grade
        )
    grade_badge.short_description = "Grade"

    def remark_display(self, obj):
        return obj.get_remark_display()
    remark_display.short_description = "Remark"
    remark_display.admin_order_field = 'remark'


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

# =============================================================
# SUBJECT ADMIN
# =============================================================

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display  = ['name', 'code', 'is_core', 'grade_count', 'result_count']
    list_filter   = ['is_core', 'grade_levels']
    list_editable = ['is_core']
    search_fields = ['name', 'code']
    filter_horizontal = ['grade_levels']   # Nice dual-list widget

    def grade_count(self, obj):
        count = obj.grade_levels.count()
        return format_html(
            '<span style="background:#eff4ff;color:#1d4ed8;'
            'padding:2px 8px;border-radius:10px;font-size:.78em;">'
            '{} grade{}</span>',
            count, 's' if count != 1 else ''
        )
    grade_count.short_description = "Grades"

    def result_count(self, obj):
        count = obj.results.count()
        return f"{count} result{'s' if count != 1 else ''}"
    result_count.short_description = "Results Entered"

# =============================================================
# TERM RECORD ADMIN
# =============================================================

@admin.register(TermRecord)
class TermRecordAdmin(admin.ModelAdmin):
    """
    Full term management interface.
    Includes actions to open/close terms and generate
    per-term finance records for all students.
    """

    list_display = [
        'term', 'session', 'status_badge', 'start_date',
        'end_date', 'progress_bar', 'weeks_left', # Renamed slightly for clarity
        'result_count', 'student_count'
    ]
    list_filter  = ['status', 'term', 'session']
    actions      = [
        'activate_term',
        'close_term',
        'generate_term_finances',
    ]

    fieldsets = (
        ('Term Identity', {
            'fields': ('term', 'session', 'status'),
            'description': (
                '⚠️ Setting status to Active will automatically '
                'close any currently active term.'
            )
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'next_term_start'),
        }),
        ('Notes for Staff', {
            'fields': ('term_notes',),
            'classes': ('collapse',),
        }),
    )

    # ── Custom list display methods ───────────────────────────

    def status_badge(self, obj):
        colors = {
            'draft':  ('#f3f4f6', '#374151', '⬜ Draft'),
            'active': ('#dcfce7', '#166534', '🟢 Active'),
            'closed': ('#fee2e2', '#991b1b', '🔴 Closed'),
        }
        bg, color, label = colors.get(
            obj.status, ('#f3f4f6', '#374151', obj.status)
        )
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;'
            'border-radius:10px;font-size:.8em;font-weight:600;">'
            '{}</span>',
            bg, color, label
        )
    status_badge.short_description = "Status"

    def progress_bar(self, obj):
        pct = obj.progress_percent()
        color = (
            '#22c55e' if pct < 70
            else '#f59e0b' if pct < 90
            else '#ef4444'
        )
        return format_html(
            '<div style="width:100px;background:#f1f5f9;'
            'border-radius:4px;height:8px;overflow:hidden;">'
            '<div style="width:{}%;background:{};height:100%;'
            'border-radius:4px;"></div></div>'
            '<span style="font-size:.75em;color:#6c757d;">'
            ' {}%</span>',
            pct, color, pct
        )
    progress_bar.short_description = "Progress"

    def weeks_left(self, obj):
        weeks = obj.weeks_remaining()
        if obj.status == 'closed':
            return 'Closed'          # ← plain string, no format_html needed
        color = '#22c55e' if weeks > 4 else '#f59e0b' if weeks > 2 else '#ef4444'
        return format_html(
            '<span style="color:{};font-weight:600;font-size:.85em;">'
            '{} wks</span>',
            color, weeks
        )
    weeks_left.short_description = "Weeks Left"

    def result_count(self, obj):
        return obj.results.count()
    result_count.short_description = "Results"

    def student_count(self, obj):
        return obj.student_finances.count()
    student_count.short_description = "Students Billed"

    # ── Admin actions ─────────────────────────────────────────

    @admin.action(description='✅ Activate selected term (closes current active term)')
    def activate_term(self, request, queryset):
        if queryset.count() > 1:
            self.message_user(
                request,
                "You can only activate one term at a time.",
                level='error'
            )
            return
        term = queryset.first()
        term.status = 'active'
        term.save()
        self.message_user(
            request,
            f"'{term}' is now the active term. "
            f"All other active terms have been closed.",
            level='success'
        )

    @admin.action(description='🔒 Close selected term (locks all results)')
    def close_term(self, request, queryset):
        count = queryset.update(status='closed')
        self.message_user(
            request,
            f"{count} term(s) closed. Results are now locked.",
            level='success'
        )

    @admin.action(
        description=(
            '💰 Generate per-term finance records '
            'for all active students'
        )
    )
    def generate_term_finances(self, request, queryset):
        """
        For each selected term, creates a TermFinance record
        for every active student using their grade's tuition fee.
        Skips students who already have a record for that term.
        """
        created_count = 0
        skipped_count = 0

        for term in queryset:
            students = Student.objects.filter(
                is_active=True
            ).select_related('grade_level')

            for student in students:
                _, created = TermFinance.objects.get_or_create(
                    student  = student,
                    term     = term,
                    defaults = {
                        'fees_due'   : student.grade_level.tuition_fee,
                        'amount_paid': 0,
                        'status'     : 'unpaid',
                    }
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        self.message_user(
            request,
            f"Created {created_count} term finance records. "
            f"Skipped {skipped_count} (already existed).",
            level='success'
        )


@admin.register(TermFinance)
class TermFinanceAdmin(admin.ModelAdmin):
    list_display  = [
        'student', 'term', 'fees_due_display',
        'paid_display', 'balance_display', 'status_badge'
    ]
    list_filter   = ['term', 'status', 'student__grade_level']
    search_fields = ['student__student_name']
    readonly_fields = []

    def fees_due_display(self, obj):
        return format_html('L${:,.2f}', obj.fees_due)
    fees_due_display.short_description = "Fees Due"

    def paid_display(self, obj):
        color = '#065f46' if obj.amount_paid >= obj.fees_due else '#92400e'
        return format_html(
            '<strong style="color:{};">L${:,.2f}</strong>',
            color, obj.amount_paid
        )
    paid_display.short_description = "Paid"

    def balance_display(self, obj):
        if not obj or not obj.pk:   # guard for unsaved/new objects
            return '—'
        bal   = obj.balance
        color = '#065f46' if bal == 0 else '#dc2626'
        return format_html(
            '<span style="color:{};font-weight:700;">L${:,.2f}</span>',
            color, bal
        )
    balance_display.short_description = "Balance"

    def status_badge(self, obj):
        colors = {
            'fully_paid': ('#d1fae5', '#065f46', '✓ Fully Paid'),
            'partial':    ('#fef3c7', '#92400e', '~ Partial'),
            'unpaid':     ('#fee2e2', '#991b1b', '✗ Unpaid'),
        }
        bg, color, label = colors.get(
            obj.status, ('#f3f4f6', '#374151', obj.status)
        )
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;'
            'border-radius:10px;font-size:.78em;">{}</span>',
            bg, color, label
        )
    status_badge.short_description = "Status"
    

# =============================================================
# RESULT ADMIN — with inline per student
# =============================================================

class ResultInline(admin.TabularInline):
    """
    Show all results for a student directly inside the
    Student admin page.
    """
    model         = Result
    extra         = 0
    readonly_fields = ['total_score', 'letter_grade', 'remark']
    fields        = [
        'subject', 'term_record',
        'ca_score', 'exam_score',
        'total_score', 'letter_grade', 'remark'
    ]
