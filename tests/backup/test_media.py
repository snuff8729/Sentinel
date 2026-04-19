from app.backup.media import MediaItem, extract_backup_html, extract_media_from_html, replace_urls_in_html

def _wrap(content_html: str, comment_html: str = "") -> str:
    """테스트용 — article-body + article-comment 영역으로 감싸기"""
    parts = [f'<div class="article-body"><div class="article-content">{content_html}</div></div>']
    if comment_html:
        parts.append(f'<div id="comment" class="article-comment">{comment_html}</div>')
    return "\n".join(parts)

def test_extract_images():
    html = _wrap('''
        <img src="//ac-p3.namu.la/20260418sac/abc123.png?expires=123&key=abc" width="800" height="600">
        <img src="//ac-p3.namu.la/20260418sac/def456.webp?expires=123&key=def" width="400" height="300">
    ''')
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 2
    assert all(i.file_type == "image" for i in items)
    assert items[0].url.startswith("https://")
    assert items[0].local_path == "articles/100/images/abc123.png"
    assert items[1].local_path == "articles/100/images/def456.webp"

def test_extract_emoticons():
    html = _wrap('''
        <img class="emoticon" data-id="227952228" src="//ac-p3.namu.la/emote.png?expires=1&key=x" width="100" height="100">
    ''')
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert items[0].file_type == "emoticon"
    assert items[0].local_path == "emoticons/227952228.png"

def test_extract_video_emoticon():
    html = _wrap('''
        <video class="emoticon" src="//ac-p3.namu.la/emote.mp4?expires=1&key=x" data-id="113951890"></video>
    ''')
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert items[0].file_type == "emoticon"
    assert items[0].local_path == "emoticons/113951890.mp4"
    assert items[0].relative_path == "../../emoticons/113951890.mp4"

def test_extract_video():
    html = _wrap('''
        <video><source src="//ac-p3.namu.la/video123.mp4?expires=1&key=x"></video>
    ''')
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert items[0].file_type == "video"
    assert items[0].local_path == "articles/100/videos/video123.mp4"

def test_extract_audio():
    html = _wrap('''
        <audio src="//ac-p3.namu.la/sound456.mp3?expires=1&key=x"></audio>
    ''')
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert items[0].file_type == "audio"
    assert items[0].local_path == "articles/100/audio/sound456.mp3"

def test_extract_gif_is_image():
    html = _wrap('''
        <img src="//ac-p3.namu.la/anim.gif?expires=1&key=x">
    ''')
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert items[0].file_type == "image"
    assert items[0].local_path == "articles/100/images/anim.gif"

def test_extract_deduplicates():
    html = _wrap('''
        <img src="//ac-p3.namu.la/same.png?expires=1&key=x">
        <img src="//ac-p3.namu.la/same.png?expires=2&key=y">
    ''')
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1

def test_extract_comment_media():
    html = _wrap(
        '<img src="//ac-p3.namu.la/body.png?expires=1&key=x">',
        '<img class="emoticon" data-store-id="999" src="//ac-p3.namu.la/emote.png?expires=1&key=x">',
    )
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 2
    types = {i.file_type for i in items}
    assert types == {"image", "emoticon"}

def test_ignores_outside_content():
    html = '''
    <nav><img src="//ac-p3.namu.la/nav.png?expires=1&key=x"></nav>
    <div class="article-body"><div class="article-content">
        <img src="//ac-p3.namu.la/body.png?expires=1&key=x">
    </div></div>
    <div class="sidebar"><img src="//ac-p3.namu.la/sidebar.png?expires=1&key=x"></div>
    '''
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert "body.png" in items[0].local_path

def test_extract_backup_html_replaces_twemoji_with_alt():
    html = '''
    <html><body>
    <div class="article-head"><h1>제목 <img class="twemoji" alt="🔞" src="/node_modules/twemoji/assets/svg/1f51e.svg"></h1></div>
    <div class="article-body"><p>본문 <img class="twemoji" alt="😀" src="/node_modules/twemoji/assets/svg/1f600.svg"></p></div>
    <div id="comment" class="article-comment"><div>댓글 <img class="twemoji" alt="👍" src="/node_modules/twemoji/assets/svg/1f44d.svg"></div></div>
    </body></html>
    '''
    result = extract_backup_html(html)
    assert "🔞" in result
    assert "😀" in result
    assert "👍" in result
    assert "twemoji" not in result
    assert "node_modules" not in result


def test_extract_media_skips_twemoji():
    html = _wrap('''
        <img class="twemoji" alt="🔞" src="/node_modules/twemoji/assets/svg/1f51e.svg">
        <img src="//ac-p3.namu.la/real.png?expires=1&key=x">
    ''')
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert "real.png" in items[0].local_path


def test_extract_backup_html():
    html = '''
    <html><head></head><body>
    <nav>네비게이션</nav>
    <div class="article-head"><h1>제목</h1></div>
    <div class="article-body"><div class="article-content"><p>본문</p></div></div>
    <div id="comment" class="article-comment"><div>댓글</div></div>
    <footer>푸터</footer>
    </body></html>
    '''
    result = extract_backup_html(html)
    assert "제목" in result
    assert "본문" in result
    assert "댓글" in result
    assert "네비게이션" not in result
    assert "푸터" not in result

def test_replace_urls_in_html():
    html = '<img src="//ac-p3.namu.la/abc.png?expires=1&amp;key=x">'
    url_map = {"https://ac-p3.namu.la/abc.png?expires=1&key=x": "./images/abc.png"}
    result = replace_urls_in_html(html, url_map)
    assert "./images/abc.png" in result
    assert "namu.la" not in result

def test_replace_urls_emoticon_relative_path():
    html = '<img class="emoticon" data-id="123" src="//ac-p3.namu.la/emote.png?expires=1&amp;key=x">'
    url_map = {"https://ac-p3.namu.la/emote.png?expires=1&key=x": "../../emoticons/123.png"}
    result = replace_urls_in_html(html, url_map)
    assert "../../emoticons/123.png" in result
