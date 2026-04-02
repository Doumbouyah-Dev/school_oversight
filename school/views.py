# school/views.py

from django.views.generic import TemplateView
from django.utils import timezone
from django.db.models import (
    Sum, Count, Q, F,
    ExpressionWrapper, DecimalField
)
from .models import Student, Finance, AcademicCalendar, Discipline
import datetime


class ProprietorDashboardView(TemplateView):
    login_url    = '/admin/login/'  # Where to send unauthenticated visitors
    redirect_field_name = 'next'    # After login, returns them to the dashboard
    template_name = 'dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today   = timezone.now().date()
        # context['total_balance'] = total_due - total_paid

        # ── Active students ────────────────────────────────────
        total_active_students = Student.objects.filter(is_active=True).count()

        # ── Gender breakdown ───────────────────────────────────
        male_count   = Student.objects.filter(is_active=True, gender='male').count()
        female_count = Student.objects.filter(is_active=True, gender='female').count()
        other_count  = Student.objects.filter(is_active=True, gender='other').count()

        # ── Collection rate ────────────────────────────────────
        totals     = Finance.objects.aggregate(
            total_paid = Sum('amount_paid'),
            total_due  = Sum('total_fees_due'),
        )
        total_paid = totals['total_paid'] or 0
        total_due  = totals['total_due']  or 0
        collection_rate = (
            round((total_paid / total_due) * 100, 1) if total_due > 0 else 0
        )
        if collection_rate >= 75:
            collection_bar_color = 'success'
        elif collection_rate >= 40:
            collection_bar_color = 'warning'
        else:
            collection_bar_color = 'danger'

        # ── Disciplinary alerts ────────────────────────────────
        seven_days_ago = today - datetime.timedelta(days=7)
        urgent_alerts  = Discipline.objects.filter(
            action_taken='expulsion',
            date__gte=seven_days_ago
        ).select_related('student')

        # ── Events ────────────────────────────────────────────
        todays_event    = AcademicCalendar.objects.filter(start_date=today).first()
        upcoming_events = AcademicCalendar.objects.filter(
            start_date__gt=today, status='upcoming'
        ).order_by('start_date')[:5]

        # ── Finance totals ─────────────────────────────────────
        fully_paid_count = Finance.objects.filter(payment_status='fully_paid').count()
        partial_count    = Finance.objects.filter(payment_status='partial').count()
        unpaid_count     = Finance.objects.filter(payment_status='unpaid').count()

        # ── Finance search ─────────────────────────────────────
        finance_search = self.request.GET.get('finance_search', '').strip()

        # ── Sorting ────────────────────────────────────────────
        sort_by  = self.request.GET.get('sort', 'name')
        sort_dir = self.request.GET.get('dir',  'asc')

        SORT_MAP = {
            'name'   : 'student__student_name',
            'gender' : 'student__gender',
            'grade'  : 'student__grade_level__order',
            'due'    : 'total_fees_due',
            'paid'   : 'amount_paid',
            'balance': None,   # handled separately via annotation
            'status' : 'payment_status',
        }

        # Safety check — ignore unknown sort keys
        if sort_by not in SORT_MAP:
            sort_by = 'name'

        # Annotate balance as a real DB expression so we can sort on it
        balance_expr = ExpressionWrapper(
            F('total_fees_due') - F('amount_paid'),
            output_field=DecimalField()
        )
        base_qs = Finance.objects.annotate(computed_balance=balance_expr)

        # Pick the ORM field for ordering
        if sort_by == 'balance':
            orm_order = (
                '-computed_balance' if sort_dir == 'desc' else 'computed_balance'
            )
        else:
            orm_field = SORT_MAP[sort_by]
            orm_order = f'-{orm_field}' if sort_dir == 'desc' else orm_field

        # Apply search
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

        # Apply sort
        finance_records = finance_records.order_by(orm_order)

        # next_dir is used in column header links to toggle direction
        next_dir = 'desc' if sort_dir == 'asc' else 'asc'

        # ── Grade breakdown ────────────────────────────────────
        grade_breakdown = Student.objects.filter(
            is_active=True
        ).values(
            'grade_level__name'
        ).annotate(
            student_count=Count('id')
        ).order_by('grade_level__order', 'grade_level__name')

        # ── Recent discipline ──────────────────────────────────
        recent_discipline = Discipline.objects.all().select_related(
            'student'
        ).order_by('-date')[:10]

        context.update({
            'today'                 : today,
            'total_active_students' : total_active_students,
            'male_count'            : male_count,
            'female_count'          : female_count,
            'other_count'           : other_count,
            'collection_rate'       : collection_rate,
            'collection_bar_color'  : collection_bar_color,
            'total_paid'            : total_paid,
            'total_due'             : total_due,
            'todays_event'          : todays_event,
            'urgent_alerts'         : urgent_alerts,
            'urgent_alert_count'    : urgent_alerts.count(),
            'upcoming_events'       : upcoming_events,
            'fully_paid_count'      : fully_paid_count,
            'partial_count'         : partial_count,
            'unpaid_count'          : unpaid_count,
            'finance_records'       : finance_records,
            'finance_search'        : finance_search,
            'finance_count'         : finance_records.count(),
            'sort_by'               : sort_by,
            'sort_dir'              : sort_dir,
            'next_dir'              : next_dir,
            'recent_discipline'     : recent_discipline,
            'grade_breakdown'       : grade_breakdown,
        })
        return context
