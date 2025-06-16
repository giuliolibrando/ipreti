from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import IndirizzoIP, Vlan

class LoginForm(AuthenticationForm):
    """Form per il login personalizzato"""
    username = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )

class IndirizzoIPForm(forms.ModelForm):
    """Form per la creazione/modifica di indirizzi IP"""
    
    class Meta:
        model = IndirizzoIP
        fields = [
            'ip', 'mac_address', 'stato', 'disponibilita',
            'responsabile', 'utente_finale', 'note', 'vlan'
        ]
        widgets = {
            'ip': forms.TextInput(attrs={'class': 'form-control'}),
            'mac_address': forms.TextInput(attrs={'class': 'form-control'}),
            'stato': forms.Select(attrs={'class': 'form-control'}),
            'disponibilita': forms.Select(attrs={'class': 'form-control'}),
            'responsabile': forms.EmailInput(attrs={'class': 'form-control'}),
            'utente_finale': forms.TextInput(attrs={'class': 'form-control'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'vlan': forms.Select(attrs={'class': 'form-control'}),
        }

class FiltroIndirizziForm(forms.Form):
    """Form per filtrare la lista degli indirizzi IP"""
    
    ip = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Cerca IP...'
        })
    )
    
    stato = forms.ChoiceField(
        choices=[('', 'Tutti')] + IndirizzoIP.STATO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    disponibilita = forms.ChoiceField(
        choices=[('', 'Tutte')] + IndirizzoIP.DISPONIBILITA_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    vlan = forms.ModelChoiceField(
        queryset=Vlan.objects.all(),
        required=False,
        empty_label="Tutte le VLAN",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    responsabile = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email responsabile...'
        })
    )
    
    anomalo = forms.ChoiceField(
        choices=[('', 'Tutti'), ('si', 'Solo anomali'), ('no', 'Solo normali')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    ) 