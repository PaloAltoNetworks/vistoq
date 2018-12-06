# Copyright (c) 2018, Palo Alto Networks
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

from django.urls import path

from mssp.views import *

app_name = 'mssp'
urlpatterns = [
    path('services', ViewServicesView.as_view()),
    path('nodes', ViewMinionsView.as_view()),
    path('deploy', DeployServiceView.as_view()),
    path('delete/<minion>/<hostname>', DeleteVMView.as_view()),
    path('results', TemplateView.as_view()),
    path('vms', ViewDeployedVmsView.as_view()),
    path('configure', ChooseSnippetView.as_view()),
    path('provision', ProvisionSnippetView.as_view())
    path('gpcs', ConfigureServiceView.as_view(snippet='cnc-conf-gpcs')),
    path('sfn', ConfigureServiceView.as_view(snippet='cnc-conf-sfn')),
    path('addon', ConfigureServiceView.as_view(snippet='cnc-conf-addon')),
    path('refarch', ConfigureServiceView.as_view(snippet='cnc-conf-refarch')),
]
