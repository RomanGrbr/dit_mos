from rest_framework import serializers
from .models import FacebookUser


class FacebookUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacebookUser
        fields = '__all__'
