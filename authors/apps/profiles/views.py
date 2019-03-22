from rest_framework import status
from rest_framework.views import APIView
from rest_framework.serializers import ValidationError
from rest_framework.generics import RetrieveAPIView, ListAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from drf_yasg.utils import swagger_auto_schema

from .models import Profile
from .renderers import ProfileJSONRenderer
from .serializers import (
    ProfileSerializer, MultipleProfileSerializer,
    FollowUnfollowSerializer, FollowerFollowingSerializer)
from .exceptions import ProfileDoesNotExist
from authors.apps.notifications.backends import notify
from authors.apps.authentication.models import User


class ProfileRetrieveAPIView(RetrieveAPIView):
    """
    Class endpoint for retreving a single user profile
    """
    permission_classes = (IsAuthenticated,)
    renderer_classes = (ProfileJSONRenderer,)
    serializer_class = ProfileSerializer

    @swagger_auto_schema(query_serializer=serializer_class,
                         responses={201: serializer_class()})
    def get(self, request, username, *args, **kwargs):
        """ function to retrieve a requested profile """
        try:
            profile = Profile.objects.select_related('user').get(
                user__username=username
            )

        except Profile.DoesNotExist:
            raise ProfileDoesNotExist

        serializer = self.serializer_class(
            profile, context={'current_user': request.user})

        return Response(serializer.data, status=status.HTTP_200_OK)

class ToggleAppNotifications(UpdateAPIView):
    permission_classes = (IsAuthenticated,)
    renderer_classes = (ProfileJSONRenderer,)
    
    def put(self, request):
        user = request.user
        user_profile = user.profile
        if user_profile.app_notifications == True:
            user_profile.app_notifications = False
            user_profile.save()
            return Response({
                "message":"you have turned app notifications off"},
                status=status.HTTP_200_OK)
        else:
            user_profile.app_notifications = True
            user_profile.save()
            return Response({
                "message":"you have turned app notifications on"},
                status=status.HTTP_200_OK)

class ToggleEmailNotifications(UpdateAPIView):
    permission_classes = (IsAuthenticated,)
    renderer_classes = (ProfileJSONRenderer,)
    
    def put(self, request):
        user = request.user
        user_profile = user.profile
        if user_profile.email_notifications == True:
            user_profile.email_notifications = False
            user_profile.save()
            return Response({
                "message":"you have turned email notifications off"},
                status=status.HTTP_200_OK)
        else:
            user_profile.email_notifications = True
            user_profile.save()
            return Response({
                "message":"you have turned email notifications on"},
                status=status.HTTP_200_OK)


class ProfilesListAPIView(ListAPIView):
    """This class allows authenticated users to get all profiles
    Get:
    Profiles
    """
    permission_classes = (IsAuthenticated,)
    queryset = Profile.objects.all()
    serializer_class = MultipleProfileSerializer


class FollowUnfollowAPIView(APIView):
    """
    This class contains endpoints for following/unfollowing users
    """
    permission_classes = (IsAuthenticated,)
    renderer_classes = (ProfileJSONRenderer,)
    serializer_class = ProfileSerializer

    def post(self, request, username):
        """Follow"""

        # see if user to be followed
        # exists
        try:
            to_be_followed = Profile.objects.get(user__username=username)
        except Profile.DoesNotExist:
            raise ProfileDoesNotExist

        # Check if user is trying to
        # follow themselves
        if request.user.id == to_be_followed.id:
            raise ValidationError("Nice try, you cannot follow yourself")

        already_followed = Profile.objects.filter(
            pk=request.user.pk, followings=to_be_followed.pk).exists()
        if already_followed:
            return Response({
                'error': f'You are already following {username}'
            }, status=status.HTTP_406_NOT_ACCEPTABLE)

        request.user.profile.followings.add(to_be_followed)
        request.user.save()

        serializer = FollowUnfollowSerializer(request.user.profile)
        message = {
            "message": f"You are now following {username}",
            "user": serializer.data
        }
        just_followed = User.objects.get(pk=to_be_followed.pk)
        notify.user_followed(request, just_followed)
        return Response(message, status=status.HTTP_200_OK)

    def delete(self, request, username):
        """Follow"""

        # see if user to be followed
        # exists
        try:
            to_be_unfollowed = Profile.objects.get(user__username=username)
        except Profile.DoesNotExist:
            raise ProfileDoesNotExist

        # Check if user is trying to
        # follow themselves
        if request.user.id == to_be_unfollowed.id:
            raise ValidationError("Nice try, that is not possible")

        following = Profile.objects.filter(
            pk=request.user.pk, followings=to_be_unfollowed.pk).exists()
        if not following:
            return Response({
                'error': f'You are not following {username}'},
                status=status.HTTP_406_NOT_ACCEPTABLE)

        request.user.profile.followings.remove(to_be_unfollowed)
        request.user.save()

        serializer = FollowUnfollowSerializer(request.user.profile)
        message = {
            "message": f"You just unfollowed {username}",
            "user": serializer.data
        }
        return Response(message, status=status.HTTP_200_OK)


class FollowerFollowingAPIView(ListAPIView):
    """
    This API returns a list of user followers and following
    """
    serializer_class = ProfileSerializer

    def get_queryset(self, username):
        try:
            user = Profile.objects.get(user__username=username)
        except Profile.DoesNotExist:
            raise ProfileDoesNotExist

        followed_friends = user.followings.all()
        following_friends = user.followers.all()
        return {
            "followed": followed_friends,
            "followers": following_friends
        }

    def get(self, request, username, format=None):
        """Returns the user's followed user"""
        following_dict = self.get_queryset(username)

        follower_serializer = FollowerFollowingSerializer(
            following_dict['followed'],
            many=True,
            context={'current_user': request.user})
        following_serializer = FollowerFollowingSerializer(
            following_dict['followers'],
            many=True,
            context={'current_user': request.user})

        message = {
            "message": f"{username}'s statistics:",
            "Followers": following_serializer.data,
            "Following": follower_serializer.data
        }
        return Response(message, status=status.HTTP_200_OK)
