from app.backup.media import MediaItem, extract_media_from_html, replace_urls_in_html

def test_extract_images():
    html = '''
    <div class="article-content">
        <img src="//ac-p3.namu.la/20260418sac/abc123.png?expires=123&key=abc" width="800" height="600">
        <img src="//ac-p3.namu.la/20260418sac/def456.webp?expires=123&key=def" width="400" height="300">
    </div>
    '''
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 2
    assert all(i.file_type == "image" for i in items)
    assert items[0].url.startswith("https://")
    assert items[0].local_path == "articles/100/images/abc123.png"
    assert items[1].local_path == "articles/100/images/def456.webp"

def test_extract_emoticons():
    html = '''
    <div class="article-content">
        <img class="arca-emoticon" data-id="227952228" src="//ac-p3.namu.la/emote.png?expires=1&key=x" width="100" height="100">
    </div>
    '''
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert items[0].file_type == "emoticon"
    assert items[0].local_path == "emoticons/227952228.png"

def test_extract_video():
    html = '''
    <div class="article-content">
        <video><source src="//ac-p3.namu.la/video123.mp4?expires=1&key=x"></video>
    </div>
    '''
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert items[0].file_type == "video"
    assert items[0].local_path == "articles/100/videos/video123.mp4"

def test_extract_audio():
    html = '''
    <div class="article-content">
        <audio src="//ac-p3.namu.la/sound456.mp3?expires=1&key=x"></audio>
    </div>
    '''
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert items[0].file_type == "audio"
    assert items[0].local_path == "articles/100/audio/sound456.mp3"

def test_extract_gif_is_image():
    html = '''
    <div class="article-content">
        <img src="//ac-p3.namu.la/anim.gif?expires=1&key=x">
    </div>
    '''
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert items[0].file_type == "image"
    assert items[0].local_path == "articles/100/images/anim.gif"

def test_extract_deduplicates():
    html = '''
    <div class="article-content">
        <img src="//ac-p3.namu.la/same.png?expires=1&key=x">
        <img src="//ac-p3.namu.la/same.png?expires=2&key=y">
    </div>
    '''
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1

def test_replace_urls_in_html():
    html = '<img src="//ac-p3.namu.la/abc.png?expires=1&amp;key=x">'
    url_map = {"https://ac-p3.namu.la/abc.png?expires=1&key=x": "./images/abc.png"}
    result = replace_urls_in_html(html, url_map)
    assert "./images/abc.png" in result
    assert "namu.la" not in result

def test_replace_urls_emoticon_relative_path():
    html = '<img class="arca-emoticon" data-id="123" src="//ac-p3.namu.la/emote.png?expires=1&amp;key=x">'
    url_map = {"https://ac-p3.namu.la/emote.png?expires=1&key=x": "../../emoticons/123.png"}
    result = replace_urls_in_html(html, url_map)
    assert "../../emoticons/123.png" in result
