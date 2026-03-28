"""
Workspace API Serializers.
"""
from rest_framework import serializers
from .models import Workspace


class WorkspaceSerializer(serializers.ModelSerializer):
    """
    Serializer for Workspace model.
    """

    class Meta:
        model = Workspace
        fields = [
            'id',
            'name',
            'status',
            'container_id',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'status', 'container_id', 'created_at', 'updated_at']


class CreateWorkspaceSerializer(serializers.Serializer):
    """
    Serializer for creating a new workspace.
    """

    name = serializers.CharField(max_length=100, help_text='Name for the new workspace')