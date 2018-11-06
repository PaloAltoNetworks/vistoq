from django import forms


class SimpleDemoForm(forms.Form):
    customer_name = forms.CharField(label='Customer Name', max_length=100)
    service_tier = forms.ChoiceField(choices=(('gold', 'Gold'), ('silver', 'Silver'), ('bronze', 'Bronze')))
    platform_sizing = forms.ChoiceField(choices=(('small', 'Small'), ('medium', 'Medium'), ('large', 'Large')))
    service_term = forms.ChoiceField(choices=(('3', '3 Year'), ('2', '2 Year'), ('1', '1 Year')))


class DeployServiceForm(forms.Form):
    minion = forms.ChoiceField(choices=())
    vm_name = forms.CharField(label='Firewall Hostname', initial='Pan-OS FW')
    left_bridge = forms.CharField(label='Untrust Bridge', initial='Untrust')
    right_bridge = forms.CharField(label='Trust Bridge', initial='Trust')
    admin_username = forms.CharField(label='Administrator Username', initial='admin')
    admin_password = forms.CharField(label='Administrator Password', initial='admin', widget=forms.PasswordInput)
    vm_auth_key = forms.CharField(label='Administrator Password', initial='admin')
    panorama_ip = forms.GenericIPAddressField(label='Panorama IP', initial='0.0.0.0')
    auth_key = forms.CharField(label='Auth Code', initial='000000')
