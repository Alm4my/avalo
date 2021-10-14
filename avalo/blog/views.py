from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.core.mail import send_mail
from django.core.paginator import PageNotAnInteger, Paginator, EmptyPage
from django.db.models import Count
from django.shortcuts import render, get_object_or_404
from taggit.models import Tag

from blog.forms import EmailPostForm, CommentForm, SearchForm
from blog.models import Post


def post_share(request, post_id):
    # retrieve post by id
    post = get_object_or_404(Post, id=post_id, status='published')
    # form is empty in case of GET request
    form = EmailPostForm()
    sent = False

    if request.method == 'POST':
        # form was submitted
        form = EmailPostForm(request.POST)
        if form.is_valid():
            # fields passed validation
            cd = form.cleaned_data
            # send email
            post_url = request.build_absolute_uri(post.get_absolute_url())
            subject = f"{cd['name']} recommends you read {post.title}"
            message = f"Read {post.title} at {post_url}\n\n" \
                      f"{cd['name']}'s comments: {cd['comments']}"
            send_mail(subject, message, 'admin@elcorvo', [cd['to']])
            sent = True

    return render(request, 'blog/post/share.html', {'post': post,
                                                    'form': form,
                                                    'sent': sent})


def post_detail(request, year, month, day, post):
    post = get_object_or_404(Post, slug=post,
                             status='published',
                             publish__year=year,
                             publish__month=month,
                             publish__day=day)

    # list of active comments for specific post
    comments = post.comments.filter(active=True)
    new_comment = None
    comment_form = CommentForm()

    # get tags for current post
    tags = post.tags.all()

    if request.method == 'POST':
        # a comment was posted
        comment_form = CommentForm(data=request.POST)
        if comment_form.is_valid():
            # create comment object without saving it to the db
            new_comment = comment_form.save(commit=False)
            # assign current post to comment
            new_comment.post = post
            # save to db
            new_comment.save()

    # list of similar posts
    post_tag_ids = post.tags.values_list('id', flat=True)
    similar_posts = Post.published.filter(tags__in=post_tag_ids)
    similar_posts = \
        similar_posts \
        .annotate(same_tags=Count('tags')) \
        .exclude(id=post.id) \
        .order_by('-same_tags', '-publish')[:4]

    return render(request, 'blog/post/detail.html', {'post': post,
                                                     'comments': comments,
                                                     'new_comment': new_comment,
                                                     'comment_form': comment_form,
                                                     'similar_posts': similar_posts,
                                                     'tags': tags})


def post_list(request, tag_slug=None):
    object_list = Post.published.all()

    tag = None
    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        object_list = object_list.filter(tags__in=[tag])

    paginator = Paginator(object_list, 3)  # 3 posts per page
    page = request.GET.get('page')

    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        # if page is not an integer deliver the first page
        posts = paginator.page(1)
    except EmptyPage:
        # if page is out of range deliver last page of results
        posts = paginator.page(paginator.num_pages)

    return render(request, 'blog/post/list.html', {'page': page,
                                                   'posts': posts,
                                                   'tag': tag})


def post_search(request):
    form = SearchForm()
    query = None
    results = []
    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            search_vector = \
                SearchVector('title', weight='A') + \
                SearchVector('body', weight='B')
            search_query = SearchQuery(query)
            results = Post.published.annotate(
                search=search_vector,  # search multiple fields with SearchVector
                rank=SearchRank(search_vector, search_query)
            ).filter(rank__gte=0.3) \
                .order_by('-rank')  # order the results by relevancy

    return render(request, 'blog/post/search.html', {'form': form,
                                                     'query': query,
                                                     'results': results})
