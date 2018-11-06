from django.urls import path

from mssp.views import *

app_name = 'mssp'
urlpatterns = [
    path('services', ViewServicesView.as_view()),
    path('nodes', ViewMinionsView.as_view()),
    path('deploy', DeployServiceView.as_view()),
    path('vms', ViewDeployedVmsView.as_view()),
    path('results', TemplateView.as_view(template_name='mssp/results.html')),
]
