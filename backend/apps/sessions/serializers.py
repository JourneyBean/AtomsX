"""
Session API Serializers.
"""
from rest_framework import serializers
from .models import Session


class MessageSerializer(serializers.Serializer):
    """
    Serializer for a single message.
    """
    id = serializers.CharField(read_only=True)
    role = serializers.CharField()
    content = serializers.CharField()
    timestamp = serializers.DateTimeField()
    status = serializers.CharField()


class SessionSerializer(serializers.ModelSerializer):
    """
    Serializer for Session model.
    """

    class Meta:
        model = Session
        fields = [
            'id',
            'workspace_id',
            'user_id',
            'messages',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user_id', 'status', 'created_at', 'updated_at']


class SendMessageSerializer(serializers.Serializer):
    """
    Serializer for sending a message to the Agent.
    """

    content = serializers.CharField(help_text='Message content to send to the Agent')