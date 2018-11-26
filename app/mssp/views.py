# some_app/views.py
import json

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.views.generic import TemplateView, RedirectView
from django.views.generic.edit import FormView

from mssp.forms import SimpleDemoForm
from mssp.lib import pan_utils
from mssp.lib import salt_utils
from mssp.lib import snippet_utils


class MSSPBaseAuth(LoginRequiredMixin):
    login_url = '/login'


class MSSPView(MSSPBaseAuth, TemplateView):
    template_name = "mssp/index.html"


class MSSPBaseFormView(FormView):
    overrides = {}

    @staticmethod
    def generate_dynamic_form(service):
        dynamic_form = forms.Form()
        for variable in service['variables']:
            field_name = variable['name']
            type_hint = variable['type_hint']
            description = variable['description']
            default = variable['default']
            # FIXME - set form field type based on type_hint
            dynamic_form.fields[field_name] = forms.CharField(label=description, initial=default)

        return dynamic_form


class ConfigureServiceView(MSSPBaseAuth, MSSPBaseFormView):
    template_name = 'mssp/simple_demo.html'
    form_class = SimpleDemoForm
    success_url = '/'

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        service_name = form.cleaned_data['service_tier']
        customer_name = form.cleaned_data['customer_name']
        service_term = form.cleaned_data['service_term']
        service = snippet_utils.load_snippet_with_name(service_name)
        print(service)
        dynamic_form = self.generate_dynamic_form(service)
        context = self.get_context_data()
        context['customer_name'] = customer_name
        context['service_term'] = service_term
        context['service'] = service
        context['form'] = dynamic_form
        return render(self.request, 'mssp/configure_service.html', context=context)


class ProvisionServiceView(MSSPBaseAuth, FormView):
    """
    Provision Service View - This view uses the Base Auth and Form View
    The posted view is actually a dynamically generated form so the forms.Form will actually be blank
    use form_valid as it will always be true in this case.
    """
    template_name = 'mssp/simple_demo.html'
    form_class = forms.Form
    success_url = '/mssp/services'

    def form_valid(self, form):
        """
        form_valid is always called on a blank / new form, so this is essentially going to get called on every POST
        self.request.POST should contain all the variables defined in the service identified by the hidden field
        'service_id'
        :param form: blank form data from request
        :return: render of a success template after service is provisioned
        """
        service_name = self.request.POST.get('service_id', '')
        customer_name = self.request.POST.get('customer_name', '')

        if service_name == '':
            # FIXME - add an ERROR page and message here
            print('No Service ID found!')
            return super().form_valid(form)

        service = snippet_utils.load_snippet_with_name(service_name)
        jinja_context = dict()

        jinja_context['customer_name'] = customer_name
        jinja_context['service_tier'] = service_name

        for v in service['variables']:
            if self.request.POST.get(v['name']):
                jinja_context[v['name']] = self.request.POST.get(v['name'])
            else:
                # FIXME - add an ERROR page and message here
                print('Required Variable not found on request!')
                return super().form_valid(form)

        # we now have a jinja context that contains all our variables and the user supplied inputs
        # FIXME - add pan.xapi stuff here to handle this stuff!
        print(jinja_context)

        # check if we need to ensure a baseline exists before hand
        if 'extends' in service and service['extends'] is not None:
            # prego (it's in there)
            baseline = service['extends']
            baseline_service = snippet_utils.load_snippet_with_name(baseline)
            # FIX for https://github.com/nembery/vistoq2/issues/5
            if 'variables' in baseline_service:
                for v in baseline_service['variables']:
                    # FIXME - Should include a way show this in UI so we have POSTED values available
                    jinja_context[v] = baseline_service['variables'][v]['default']

            if baseline_service is not None:
                # check the panorama config to see if it's there or not
                if not pan_utils.validate_snippet_present(baseline_service, jinja_context):
                    # no prego (it's not in there)
                    print('Pushing configuration dependency: %s' % baseline_service['name'])
                    # make it prego
                    pan_utils.push_service(baseline_service, jinja_context)

        if not pan_utils.validate_snippet_present(service, jinja_context):
            print('Pushing new service: %s' % service['name'])
            pan_utils.push_service(service, jinja_context)
        else:
            print('This service was already configured on the server')

        return super().form_valid(form)


class ViewServicesView(MSSPBaseAuth, TemplateView):
    template_name = "mssp/service_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_list = pan_utils.get_device_groups_from_panorama()
        context['service_list'] = service_list
        return context


class ViewMinionsView(MSSPBaseAuth, TemplateView):
    template_name = "mssp/minion_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        salt_util = salt_utils.SaltUtil()
        minion_list = salt_util.get_minion_list()
        context['minion_list'] = minion_list
        return context


class MSSPBaseDynamicFormView(MSSPBaseFormView):
    form_class = forms.Form
    template_name = 'mssp/dynamic_form.html'
    success_url = '/mssp/results'
    snippet = ''
    header = 'Vistoq MSSP'
    title = 'Deploy'
    action = '/mssp/deploy'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = snippet_utils.load_snippet_with_name(self.snippet)
        form = self.generate_dynamic_form(service)
        context['form'] = form
        context['header'] = self.header
        return context


class DeployServiceView(MSSPBaseAuth, MSSPBaseDynamicFormView):
    template_name = 'mssp/deploy_service.html'
    snippet = 'provision_firewall'

    def form_valid(self, form):
        print('Here we go deploying')
        jinja_context = dict()
        service = snippet_utils.load_snippet_with_name('provision_firewall')

        for v in service['variables']:
            if self.request.POST.get(v['name']):
                jinja_context[v['name']] = self.request.POST.get(v['name'])

        salt_util = salt_utils.SaltUtil()
        res = salt_util.deploy_service(service, jinja_context)
        print(res)
        context = dict()
        context['results'] = res
        return render(self.request, 'mssp/results.html', context=context)


class ViewDeployedVmsView(MSSPBaseAuth, MSSPBaseDynamicFormView):
    """
    Show all the VMs currently deployed on the compute node

    GET will show the dynamic form based on the 'show_deployed_vms_on_node' snippet

    POST will load the snippet and execute it against
    """
    snippet = 'show_deployed_vms_on_node'
    header = 'Vistoq MSSP'
    title = 'Show Deployed VMs on Node'
    action = '/mssp/vms'

    def form_valid(self, form):
        print('Here we go deploying')
        jinja_context = dict()
        service = snippet_utils.load_snippet_with_name(self.snippet)

        for v in service['variables']:
            if self.request.POST.get(v['name']):
                jinja_context[v['name']] = self.request.POST.get(v['name'])

        minion = self.request.POST.get('minion')
        salt_util = salt_utils.SaltUtil()
        res = salt_util.deploy_service(service, jinja_context)
        context = dict()

        try:
            response_obj = json.loads(res)
            # {"return": [{"compute-01.c.vistoq-demo.internal": {"shoaf1": "shutdown", "stuart1": "shutdown"}}]}
            fm = response_obj['return'][0]
            vms = list()
            if minion in fm:
                minion_dict = response_obj['return'][0][minion]
                for m in minion_dict:
                    vm_detail = dict()
                    vm_detail['hostname'] = m
                    vm_detail['status'] = minion_dict[m]
                    vms.append(vm_detail)

                context['vms'] = vms
                return render(self.request, 'mssp/deployed_vms.html', context=context)
            else:
                context['results'] = response_obj['return'][0]
                return render(self.request, 'mssp/results.html', context=context)
        except ValueError as ve:
            print('Could not parse json')
            print(ve)
            context['results'] = {'Error': 'Could not get deployed VMs list!'}
            return render(self.request, 'mssp/results.html', context=context)


class DeleteVMView(RedirectView):

    def get_redirect_url(self, *args, **kwargs):
        hostname = self.kwargs['hostname']
        minion = self.kwargs['minion']
        service = snippet_utils.load_snippet_with_name('delete_single_vm')
        jinja_context = dict()
        for v in service['variables']:
            if self.request.POST.get(v['name']):
                jinja_context[v['name']] = self.request.POST.get(v['name'])

        salt_util = salt_utils.SaltUtil()
        res = salt_util.deploy_service(service, jinja_context)
        print(res)
        print('deleting hostname %s' % hostname)
        return '/mssp/vms'
