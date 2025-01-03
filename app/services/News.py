import html
import re
from unicodedata import category

import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime
from typing import List, Dict
class News:
    def __init__(self):
        self.url = f"https://news.google.com/rss/headlines/section/topics/POLITICS?hl=ko&gl=KR&ceid=KR:ko&when=1h"

    def __clean_html(self, html_text: str) -> str:
        """
        HTML 태그 제거 및 특수문자 디코딩
        Args:
            html_text: 정리할 HTML 텍스트
        Returns:
            정리된 텍스트
        """
        # HTML 엔티티 디코딩
        text = html.unescape(html_text)  # escape 대신 unescape 사용

        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', text)

        # 여러 줄 공백을 한 줄로
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def __format_date(self, date_str: str) -> str:
        """
        날짜 포맷 변경
        Args:
            date_str: RSS에서 받은 날짜 문자열
        Returns:
            변환된 날짜 문자열
        """
        try:
            date_obj = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
            return date_obj.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return date_str

    def get(self) -> Dict:
        """
        뉴스 데이터 가져오기
        Returns:
            카테고리별 뉴스 아이템을 포함하는 딕셔너리
        """
        response = requests.get(self.url)
        root = ET.fromstring(response.text)
        items = root.findall('.//item')

        news_dict = {}
        for i, item in enumerate(items, 1):
            # 데이터 추출
            title = item.find('title')
            description = item.find('description')
            pubDate = item.find('pubDate')
            source = item.find('source')

            # 데이터 정리
            news_dict[f'news_{i}'] = {
                'title': self.__clean_html(title.text) if title is not None else "",
                'content': self.__clean_html(description.text) if description is not None else "",
                'pubDate': self.__format_date(pubDate.text) if pubDate is not None else "",
                'source': source.text if source is not None else ""
            }

        return news_dict