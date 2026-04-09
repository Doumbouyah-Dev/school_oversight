# school/forms.py

from django import forms
from .models import TermRecord
import datetime


class DateRangeForm(forms.Form):
    """
    Validates and parses the ?from= and ?to= GET parameters.
    Also handles preset shortcuts like ?preset=this_month.
    """

    date_from = forms.DateField(
        required = False,
        widget   = forms.DateInput(attrs={'type': 'date'}),
        label    = "From"
    )
    date_to = forms.DateField(
        required = False,
        widget   = forms.DateInput(attrs={'type': 'date'}),
        label    = "To"
    )
    preset = forms.ChoiceField(
        required = False,
        choices  = [
            ('',            'Custom range'),
            ('today',       'Today'),
            ('this_week',   'This week'),
            ('last_week',   'Last week'),
            ('this_month',  'This month'),
            ('last_month',  'Last month'),
            ('this_term',   'This term'),
            ('last_30',     'Last 30 days'),
            ('last_90',     'Last 90 days'),
        ],
        label = "Quick select"
    )

    def clean(self):
        cleaned = super().clean()
        d_from  = cleaned.get('date_from')
        d_to    = cleaned.get('date_to')

        if d_from and d_to and d_from > d_to:
            raise forms.ValidationError(
                "Start date cannot be after end date."
            )
        return cleaned

    def resolve_range(self):
        """
        Returns (date_from, date_to) as a tuple of date objects,
        applying any preset shortcuts first.

        Called by the view after form.is_valid().
        """
        today  = datetime.date.today()
        preset = self.cleaned_data.get('preset', '')

        if preset == 'today':
            return today, today

        elif preset == 'this_week':
            start = today - datetime.timedelta(days=today.weekday())
            return start, today

        elif preset == 'last_week':
            start = today - datetime.timedelta(days=today.weekday() + 7)
            end   = start + datetime.timedelta(days=6)
            return start, end

        elif preset == 'this_month':
            return today.replace(day=1), today

        elif preset == 'last_month':
            first_this  = today.replace(day=1)
            last_prev   = first_this - datetime.timedelta(days=1)
            first_prev  = last_prev.replace(day=1)
            return first_prev, last_prev

        elif preset == 'last_30':
            return today - datetime.timedelta(days=30), today

        elif preset == 'last_90':
            return today - datetime.timedelta(days=90), today

        elif preset == 'this_term':
            term = TermRecord.objects.filter(status='active').first()
            if term:
                return term.start_date, today
            return today - datetime.timedelta(days=90), today

        else:
            # Custom range — use whatever the user typed
            d_from = self.cleaned_data.get('date_from')
            d_to   = self.cleaned_data.get('date_to')
            # Defaults: last 30 days if nothing entered
            if not d_from:
                d_from = today - datetime.timedelta(days=30)
            if not d_to:
                d_to = today
            return d_from, d_to