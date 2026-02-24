from django.urls import path
from .views import MemberListView, MemberDetailView, MemberStatusView, MemberStatsView

urlpatterns = [
    path('members/',                    MemberListView.as_view()),
    path('members/status/',             MemberStatusView.as_view()),
    path('members/stats/',              MemberStatsView.as_view()),
    path('members/<str:facebook_id>/',  MemberDetailView.as_view()),
]
