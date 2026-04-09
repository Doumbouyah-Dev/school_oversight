import datetime
from django.db import models
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView
from django.utils import timezone
from django.db.models import (
    Avg, Sum, Count, Q, F,
    ExpressionWrapper, DecimalField
)
from .models import (
    GradeLevel, Student, Finance, PaymentTransaction,
    AcademicCalendar, Discipline, AuditLog, Subject, 
    TermRecord, Result, TermFinance, GradeLevel
)
import datetime
from .forms import DateRangeForm

class ProprietorDashboardView(LoginRequiredMixin, TemplateView):
    """
    LoginRequiredMixin handles authentication.
    If not logged in -> redirect to login_url.
    """
    login_url = '/admin/login/'
    redirect_field_name = 'next'
    template_name = 'dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today   = timezone.now().date()

        # ══════════════════════════════════════════════════════
        # DATE RANGE RESOLUTION
        # ══════════════════════════════════════════════════════
        range_form = DateRangeForm(self.request.GET or None)

        if range_form.is_valid():
            date_from, date_to = range_form.resolve_range()
            active_preset = range_form.cleaned_data.get('preset', '')
        else:
            # Default: this month
            date_from     = today.replace(day=1)
            date_to       = today
            active_preset = 'this_month'

        # Human-readable label for the active filter
        preset_labels = {
            ''           : 'Custom range',
            'today'      : 'Today',
            'this_week'  : 'This week',
            'last_week'  : 'Last week',
            'this_month' : 'This month',
            'last_month' : 'Last month',
            'this_term'  : 'This term',
            'last_30'    : 'Last 30 days',
            'last_90'    : 'Last 90 days',
        }
        range_label = (
            preset_labels.get(active_preset)
            or f"{date_from} → {date_to}"
        )

        # ══════════════════════════════════════════════════════
        # STUDENTS
        # ══════════════════════════════════════════════════════
        total_active_students = Student.objects.filter(
            is_active=True
        ).count()

        # New enrollments within the date range
        new_enrollments = Student.objects.filter(
            date_enrolled__gte = date_from,
            date_enrolled__lte = date_to,
        ).count()

        male_count   = Student.objects.filter(
            is_active=True, gender='male'
        ).count()
        female_count = Student.objects.filter(
            is_active=True, gender='female'
        ).count()
        other_count  = Student.objects.filter(
            is_active=True, gender='other'
        ).count()

        # ══════════════════════════════════════════════════════
        # FINANCE (all-time totals — not date-filtered)
        # ══════════════════════════════════════════════════════
        totals     = Finance.objects.aggregate(
            total_paid = Sum('amount_paid'),
            total_due  = Sum('total_fees_due'),
        )
        total_paid = totals['total_paid'] or 0
        total_due  = totals['total_due']  or 0
        total_outstanding = total_due - total_paid

        collection_rate = (
            round((total_paid / total_due) * 100, 1)
            if total_due > 0 else 0
        )
        if collection_rate >= 75:
            collection_bar_color = 'success'
        elif collection_rate >= 40:
            collection_bar_color = 'warning'
        else:
            collection_bar_color = 'danger'

        fully_paid_count = Finance.objects.filter(
            payment_status='fully_paid'
        ).count()
        partial_count = Finance.objects.filter(
            payment_status='partial'
        ).count()
        unpaid_count = Finance.objects.filter(
            payment_status='unpaid'
        ).count()

        # ── Finance within date range ──────────────────────────
        range_payments = PaymentTransaction.objects.filter(
            date__gte = date_from,
            date__lte = date_to,
        )
        range_collected = range_payments.aggregate(
            total = Sum('amount')
        )['total'] or 0
        range_payment_count = range_payments.count()

        # Daily breakdown for sparkline (last 7 days within range)
        daily_collections = []
        check_date = date_to
        for _ in range(7):
            day_total = PaymentTransaction.objects.filter(
                date=check_date
            ).aggregate(total=Sum('amount'))['total'] or 0
            daily_collections.append({
                'date' : check_date.strftime('%b %d'),
                'total': float(day_total),
            })
            check_date -= datetime.timedelta(days=1)
        daily_collections.reverse()

        # ══════════════════════════════════════════════════════
        # FINANCE SEARCH + SORT (unchanged from Feature 4)
        # ══════════════════════════════════════════════════════
        finance_search = self.request.GET.get(
            'finance_search', ''
        ).strip()
        sort_by  = self.request.GET.get('sort', 'name')
        sort_dir = self.request.GET.get('dir',  'asc')

        SORT_MAP = {
            'name'   : 'student__student_name',
            'gender' : 'student__gender',
            'grade'  : 'student__grade_level__order',
            'due'    : 'total_fees_due',
            'paid'   : 'amount_paid',
            'balance': None,
            'status' : 'payment_status',
        }
        if sort_by not in SORT_MAP:
            sort_by = 'name'

        balance_expr = ExpressionWrapper(
            F('total_fees_due') - F('amount_paid'),
            output_field=DecimalField()
        )
        base_qs = Finance.objects.annotate(
            computed_balance=balance_expr
        )

        if sort_by == 'balance':
            orm_order = (
                '-computed_balance'
                if sort_dir == 'desc'
                else 'computed_balance'
            )
        else:
            orm_field = SORT_MAP[sort_by]
            orm_order = (
                f'-{orm_field}'
                if sort_dir == 'desc'
                else orm_field
            )

        if finance_search:
            finance_records = base_qs.filter(
                Q(student__student_name__icontains=finance_search) |
                Q(student__grade_level__name__icontains=finance_search) |
                Q(payment_status__icontains=finance_search)
            ).select_related('student', 'student__grade_level')
        else:
            finance_records = base_qs.select_related(
                'student', 'student__grade_level'
            )

        finance_records = finance_records.order_by(orm_order)
        next_dir = 'desc' if sort_dir == 'asc' else 'asc'

        # ══════════════════════════════════════════════════════
        # DISCIPLINE — filtered by date range
        # ══════════════════════════════════════════════════════
        seven_days_ago = today - datetime.timedelta(days=7)
        urgent_alerts  = Discipline.objects.filter(
            action_taken = 'expulsion',
            date__gte    = seven_days_ago,
        ).select_related('student')

        # Date-range filtered discipline
        range_discipline = Discipline.objects.filter(
            date__gte = date_from,
            date__lte = date_to,
        ).select_related('student').order_by('-date')

        range_discipline_count = range_discipline.count()

        # Discipline breakdown by action type within range
        discipline_breakdown = (
            range_discipline
            .values('action_taken')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # Recent discipline for the table (still latest 10)
        recent_discipline = Discipline.objects.select_related(
            'student'
        ).order_by('-date')[:10]

        # ══════════════════════════════════════════════════════
        # EVENTS — filtered by date range
        # ══════════════════════════════════════════════════════
        todays_event = AcademicCalendar.objects.filter(
            start_date=today
        ).first()

        upcoming_events = AcademicCalendar.objects.filter(
            start_date__gt = today,
            status         = 'upcoming',
        ).order_by('start_date')[:5]

        # Events within date range
        range_events = AcademicCalendar.objects.filter(
            start_date__gte = date_from,
            start_date__lte = date_to,
        ).order_by('start_date')
        range_event_count = range_events.count()

        # ══════════════════════════════════════════════════════
        # PAYMENTS — today / month totals
        # ══════════════════════════════════════════════════════
        todays_data = PaymentTransaction.objects.filter(
            date=today
        ).aggregate(total=Sum('amount'), count=Count('id'))
        todays_total = todays_data['total'] or 0
        todays_count = todays_data['count'] or 0

        monthly_collections = PaymentTransaction.objects.filter(
            date__gte=today.replace(day=1)
        ).aggregate(total=Sum('amount'))['total'] or 0

        recent_payments = PaymentTransaction.objects.select_related(
            'finance__student',
            'finance__student__grade_level',
        ).order_by('-date', '-created_at')[:15]

        # ══════════════════════════════════════════════════════
        # AUDIT LOG — filtered by date range
        # ══════════════════════════════════════════════════════
        recent_activity = AuditLog.objects.filter(
            timestamp__date__gte = date_from,
            timestamp__date__lte = date_to,
        ).select_related('user').order_by('-timestamp')[:20]

        audit_today = AuditLog.objects.filter(
            timestamp__date=today
        ).count()

        # Audit summary by action type within range
        audit_summary = (
            AuditLog.objects.filter(
                timestamp__date__gte = date_from,
                timestamp__date__lte = date_to,
            )
            .values('action')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # ══════════════════════════════════════════════════════
        # TERM + ACADEMIC (unchanged from Feature 5)
        # ══════════════════════════════════════════════════════
        current_term   = TermRecord.objects.filter(
            status='active'
        ).first()
        all_terms      = TermRecord.objects.order_by(
            '-session', 'term'
        )

        viewed_term_id = self.request.GET.get('term')
        if viewed_term_id:
            try:
                viewed_term = TermRecord.objects.get(
                    pk=viewed_term_id
                )
            except TermRecord.DoesNotExist:
                viewed_term = current_term
        else:
            viewed_term = current_term

        if current_term:
            term_progress    = current_term.progress_percent()
            term_weeks_left  = current_term.weeks_remaining()
            term_weeks_total = current_term.duration_weeks()
            term_events_remaining = AcademicCalendar.objects.filter(
                start_date__gte = today,
                start_date__lte = current_term.end_date,
                status__in      = ['upcoming', 'in_progress'],
            ).count()
        else:
            term_progress = term_weeks_left = term_weeks_total = 0
            term_events_remaining = 0

        if viewed_term:
            results_qs      = Result.objects.filter(
                term_record=viewed_term
            )
            total_results   = results_qs.count()
            passing_results = results_qs.filter(
                total_score__gte=40
            ).count()
            failing_results = results_qs.filter(
                total_score__lt=40
            ).count()
            overall_avg     = round(float(
                results_qs.aggregate(
                    avg=Avg('total_score')
                )['avg'] or 0
            ), 1)

            flagged_students = (
                Student.objects.filter(
                    results__term_record  = viewed_term,
                    results__letter_grade = 'F',
                    is_active             = True,
                )
                .distinct()
                .prefetch_related('grade_level')
                .annotate(fail_count=Count(
                    'results',
                    filter=models.Q(
                        results__letter_grade = 'F',
                        results__term_record  = viewed_term,
                    )
                ))
                .order_by('-fail_count')[:10]
            )

            top_performers = (
                Student.objects.filter(
                    results__term_record = viewed_term,
                    is_active            = True,
                )
                .annotate(avg_score=Avg(
                    'results__total_score',
                    filter=models.Q(
                        results__term_record=viewed_term
                    )
                ))
                .filter(avg_score__isnull=False)
                .order_by('-avg_score')[:5]
            )

            subject_averages = (
                Subject.objects.filter(
                    results__term_record=viewed_term
                )
                .annotate(
                    avg_score      = Avg('results__total_score'),
                    total_students = Count('results'),
                    fail_count     = Count(
                        'results',
                        filter=models.Q(
                            results__letter_grade='F'
                        )
                    ),
                )
                .filter(avg_score__isnull=False)
                .order_by('-avg_score')
            )

            grade_performance = (
                GradeLevel.objects.filter(
                    students__results__term_record = viewed_term,
                    students__is_active            = True,
                )
                .annotate(
                    avg_score     = Avg(
                        'students__results__total_score',
                        filter=models.Q(
                            students__results__term_record=viewed_term
                        )
                    ),
                    student_count = Count(
                        'students', distinct=True
                    ),
                )
                .filter(avg_score__isnull=False)
                .order_by('order')
            )

            grade_dist      = (
                results_qs.values('letter_grade')
                .annotate(count=Count('id'))
                .order_by('letter_grade')
            )
            grade_dist_dict = {
                item['letter_grade']: item['count']
                for item in grade_dist
            }

            term_finance_qs   = TermFinance.objects.filter(
                term=viewed_term
            )
            term_total_due    = term_finance_qs.aggregate(
                t=Sum('fees_due')
            )['t'] or 0
            term_total_paid   = term_finance_qs.aggregate(
                t=Sum('amount_paid')
            )['t'] or 0
            term_unpaid_count = term_finance_qs.filter(
                status='unpaid'
            ).count()

        else:
            total_results   = passing_results = failing_results = 0
            overall_avg     = 0
            flagged_students = top_performers = subject_averages = []
            grade_performance = []
            grade_dist_dict   = {}
            term_total_due = term_total_paid = term_unpaid_count = 0

        compare_term_id = self.request.GET.get('compare')
        compare_term    = None
        compare_avg     = None
        if compare_term_id:
            try:
                compare_term = TermRecord.objects.get(
                    pk=compare_term_id
                )
                compare_avg  = round(float(
                    Result.objects.filter(term_record=compare_term)
                    .aggregate(avg=Avg('total_score'))['avg'] or 0
                ), 1)
            except TermRecord.DoesNotExist:
                pass

        # ── Grade breakdown ────────────────────────────────────
        grade_breakdown = (
            Student.objects.filter(is_active=True)
            .values('grade_level__name')
            .annotate(student_count=Count('id'))
            .order_by('grade_level__order', 'grade_level__name')
        )

        # ══════════════════════════════════════════════════════
        # PACK CONTEXT
        # ══════════════════════════════════════════════════════
        context.update({
            'today'                 : today,

            # Date range
            'range_form'            : range_form,
            'date_from'             : date_from,
            'date_to'               : date_to,
            'active_preset'         : active_preset,
            'range_label'           : range_label,

            # Students
            'total_active_students' : total_active_students,
            'new_enrollments'       : new_enrollments,
            'male_count'            : male_count,
            'female_count'          : female_count,
            'other_count'           : other_count,

            # Finance (all-time)
            'total_paid'            : total_paid,
            'total_due'             : total_due,
            'total_outstanding'     : total_outstanding,
            'collection_rate'       : collection_rate,
            'collection_bar_color'  : collection_bar_color,
            'fully_paid_count'      : fully_paid_count,
            'partial_count'         : partial_count,
            'unpaid_count'          : unpaid_count,

            # Finance (date range)
            'range_collected'       : range_collected,
            'range_payment_count'   : range_payment_count,
            'daily_collections'     : daily_collections,

            # Finance table
            'finance_records'       : finance_records,
            'finance_search'        : finance_search,
            'finance_count'         : finance_records.count(),
            'sort_by'               : sort_by,
            'sort_dir'              : sort_dir,
            'next_dir'              : next_dir,

            # Payments
            'recent_payments'       : recent_payments,
            'todays_total'          : todays_total,
            'todays_count'          : todays_count,
            'monthly_collections'   : monthly_collections,

            # Discipline
            'urgent_alerts'         : urgent_alerts,
            'urgent_alert_count'    : urgent_alerts.count(),
            'recent_discipline'     : recent_discipline,
            'range_discipline'      : range_discipline,
            'range_discipline_count': range_discipline_count,
            'discipline_breakdown'  : discipline_breakdown,

            # Events
            'todays_event'          : todays_event,
            'upcoming_events'       : upcoming_events,
            'range_events'          : range_events,
            'range_event_count'     : range_event_count,

            # Audit
            'recent_activity'       : recent_activity,
            'audit_today'           : audit_today,
            'audit_summary'         : audit_summary,

            # Term
            'current_term'          : current_term,
            'viewed_term'           : viewed_term,
            'all_terms'             : all_terms,
            'term_progress'         : term_progress,
            'term_weeks_left'       : term_weeks_left,
            'term_weeks_total'      : term_weeks_total,
            'term_events_remaining' : term_events_remaining,
            'term_total_due'        : term_total_due,
            'term_total_paid'       : term_total_paid,
            'term_unpaid_count'     : term_unpaid_count,

            # Academic
            'total_results'         : total_results,
            'passing_results'       : passing_results,
            'failing_results'       : failing_results,
            'overall_avg'           : overall_avg,
            'flagged_students'      : flagged_students,
            'top_performers'        : top_performers,
            'subject_averages'      : subject_averages,
            'grade_performance'     : grade_performance,
            'grade_dist_dict'       : grade_dist_dict,
            'compare_term'          : compare_term,
            'compare_avg'           : compare_avg,

            # Enrollment
            'grade_breakdown'       : grade_breakdown,
        })
        return context


# ── Receipt view (from Feature 2) ─────────────────────────────

class ReceiptView(LoginRequiredMixin, DetailView):
    model           = PaymentTransaction
    template_name   = 'receipt.html'
    slug_field      = 'receipt_number'
    slug_url_kwarg  = 'receipt_number'
    login_url       = '/admin/login/'

class ReceiptView(LoginRequiredMixin, DetailView):
    """
    Renders a clean printable receipt for a single PaymentTransaction.
    """
    model = PaymentTransaction
    template_name = 'receipt.html'
    slug_field = 'receipt_number'
    slug_url_kwarg = 'receipt_number'
    login_url = '/admin/login/'