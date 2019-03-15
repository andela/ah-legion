from rest_framework import (
    generics, mixins, status
)
from rest_framework.views import APIView

from rest_framework.permissions import (
    AllowAny, IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from .renderers import ArticleJSONRenderer
from .serializers import TheArticleSerializer, LikesSerializer
from .models import Article, Like
from authors.apps.core.views import BaseManageView


# Create your views here.
class CreateArticleView(mixins.CreateModelMixin,
                        generics.GenericAPIView):
    queryset = Article.objects.all()
    permission_classes = (IsAuthenticated,)
    renderer_classes = (ArticleJSONRenderer,)
    serializer_class = (TheArticleSerializer)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        payload = request.data.get('article', {})
        # Decode token
        this_user = request.user
        payload['author'] = this_user.pk

        serializer = TheArticleSerializer(data=payload)
        serializer.is_valid(raise_exception=True)

        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class GetArticlesView(
    mixins.ListModelMixin, generics.GenericAPIView
):
    queryset = Article.objects.all()
    permission_classes = (AllowAny,)
    renderer_classes = (ArticleJSONRenderer,)
    serializer_class = (TheArticleSerializer)
    pagination_class = LimitOffsetPagination

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        # Decode token
        reply_not_found = {}
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(self.queryset, request)
        published_articles = Article.objects.filter(
            published=True, activated=True)

        if (len(published_articles) < 1):
            reply_not_found["detail"] = "No articles have been found."
            return Response(
                reply_not_found,
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class GetAnArticleView(
    mixins.RetrieveModelMixin, generics.GenericAPIView
):
    queryset = Article.objects.all()
    permission_classes = (AllowAny,)
    renderer_classes = (ArticleJSONRenderer,)
    serializer_class = (TheArticleSerializer)

    def get(self, request, slug):
        '''Get a single article'''
        found_article = Article.objects.filter(
            slug=slug, published=True,
            activated=True
        ).first()

        if found_article is not None:
            serialized = self.serializer_class(found_article)
            return Response(
                serialized.data,
                status=status.HTTP_200_OK
            )
        not_found = {}
        not_found['detail'] = "This article has not been found."
        return Response(
            not_found,
            status=status.HTTP_404_NOT_FOUND
        )


class UpdateAnArticleView(
    mixins.UpdateModelMixin, generics.GenericAPIView
):
    queryset = Article.objects.all()
    permission_classes = (IsAuthenticated,)
    renderer_classes = (ArticleJSONRenderer,)
    serializer_class = (TheArticleSerializer)
    lookup_field = "slug"

    def _edit_article(self, request, the_data):
        if self.get_object().author == request.user:

            if self.get_object().activated is False:
                invalid_entry = {
                    "detail": "This article does not exist."
                }
                return Response(
                    invalid_entry,
                    status=status.HTTP_404_NOT_FOUND
                )

            article_obj = self.get_object()
            serialized = self.serializer_class(
                article_obj, data=the_data, partial=True
            )
            serialized.is_valid(raise_exception=True)
            self.perform_update(serialized)
            if "activated" in the_data.keys()\
                    and the_data["activated"] is False:
                deleted_entry = {
                    "detail": "This article has been deleted."
                }
                return Response(
                    deleted_entry,
                    status=status.HTTP_200_OK
                )
            return Response(
                serialized.data,
                status=status.HTTP_200_OK
            )

        not_found = {
            "detail": "You are not the owner of the article."
        }
        return Response(
            not_found,
            status=status.HTTP_401_UNAUTHORIZED
        )

    def put(self, request, *args, **kwargs):
        '''This method method updates field of model article'''
        my_data = request.data.get('article', {})
        return self._edit_article(request, my_data)

    def delete(self, request, *args, **kwargs):
        '''This method performs a soft deletion of an article.'''
        soft_delete = {"activated": False}
        return self._edit_article(request, soft_delete)

    def patch(self, request, *args, **kwargs):
        '''This method is used to publish an article.'''
        new_data = self.get_object().draft
        if new_data is not None:
            publish_data = {
                "body": new_data,
                "published": True
            }
            return self._edit_article(request, publish_data)
        no_edit = {}
        no_edit["detail"] = "Draft has no data"
        return Response(
            no_edit,
            status=status.HTTP_400_BAD_REQUEST
        )


class CreateLikeView(generics.CreateAPIView):
    """This class creates a new like or dislike"""
    permission_classes = (IsAuthenticated,)
    serializer_class = LikesSerializer

    def create(self, request, slug):
        """Creates a like"""
        data = request.data
        article = Article.objects.filter(
            slug=slug, published=True, activated=True).first()
        if article is None:
            not_found = {
                "detail": "This article has not been found."
            }
            return Response(data=not_found, status=status.HTTP_404_NOT_FOUND)

        like = Like.objects.filter(
            user_id=request.user.pk, article_id=article.id).first()
        if like is not None:
            like_found = {
                "detail": "Article already liked or disliked, \
                    use another route to update."
            }
            return Response(data=like_found, status=status.HTTP_400_BAD_REQUEST)

        data['article_id'] = article.id
        data['user_id'] = request.user.pk
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class GetLikeView(generics.RetrieveAPIView):
    """Fetch like or dislike for an article"""
    permission_classes = (IsAuthenticated, )
    queryset = Like.objects.all()

    def get(self, request, slug):
        article = Article.objects.filter(
            slug=slug, published=True, activated=True).first()
        if article is None:
            not_found = {
                "detail": "This article has not been found."
            }
            return Response(data=not_found, status=status.HTTP_404_NOT_FOUND)
        like = Like.objects.filter(
            user_id=request.user.pk, article_id=article.id).first()
        if like is None:
            no_like = {
                "detail": "This user has neither liked \
                    nor disliked the article."
            }
            return Response(data=no_like, status=status.HTTP_404_NOT_FOUND)
        like_data = {"id": like.id,
                     "article_id": like.article_id.id,
                     "user_id": like.user_id.id
                     }
        return Response(data=like_data, status=status.HTTP_200_OK)


class UpdateLikeView(generics.UpdateAPIView):
    """Perfom update on likes"""
    permission_classes = (IsAuthenticated, )
    serializer_class = LikesSerializer
    queryset = Like.objects.all()

    def patch(self, request, *args, **kwargs):
        like_id = kwargs['pk']
        like = Like.objects.filter(id=like_id).first()
        if like:
            like_owner_id = like.user_id.id
            if like_owner_id != request.user.id:
                message = {
                    "detail": "This user does not own this like"
                }
                return Response(data=message, status=status.HTTP_403_FORBIDDEN)
        return self.partial_update(request, *args, **kwargs)


class DeleteLikeView(generics.DestroyAPIView):
    """Delete like"""
    permission_classes = (IsAuthenticated, )
    serializer_class = LikesSerializer
    queryset = Like.objects.all()

    def delete(self, request, *args, **kwargs):
        like_id = kwargs['pk']
        like = Like.objects.filter(id=like_id).first()
        if like:
            like_owner_id = like.user_id.id
            if like_owner_id != request.user.id:
                message = {"detail": "This user does not own this like"}
                return Response(data=message, status=status.HTTP_403_FORBIDDEN)
        return self.destroy(request, *args, **kwargs)


class CreateRetrieveLikeView(BaseManageView):
    """Handles create and retrieve likes"""
    VIEWS_BY_METHOD = {
        'POST': CreateLikeView.as_view,
        'GET': GetLikeView.as_view,
    }


class UpdateDeleteLikeView(BaseManageView):
    """Handles update and retrieve a like"""
    VIEWS_BY_METHOD = {
        'PATCH': UpdateLikeView.as_view,
        'DELETE': DeleteLikeView.as_view,
    }


class GetArticleLikesView(APIView):
    """Gets all articles' likes and dislikes"""
    permission_classes = (AllowAny, )

    def get(self, request, slug):
        article = Article.objects.filter(
            slug=slug, published=True, activated=True).first()
        if article is None:
            not_found = {
                "detail": "This article has not been found."
            }
            return Response(data=not_found, status=status.HTTP_404_NOT_FOUND)
        likes_queryset = Like.objects.filter(
            is_like=True, article_id=article.id)
        dislikes_queryset = Like.objects.filter(
            is_like=False, article_id=article.id)
        dislikes_count = dislikes_queryset.count()
        likes_count = likes_queryset.count()
        likes_dislikes = {
            "likes": likes_count,
            "dislikes": dislikes_count,
        }
        return Response(data=likes_dislikes, status=status.HTTP_200_OK)