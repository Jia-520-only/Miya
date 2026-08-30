"""
搜索模块 - 百度搜索引擎
"""

import logging

from plugins.yinmei.tools import singleton, StringUtil
from plugins.yinmei.core import SharedData
from plugins.yinmei.core.obs_controller import OBSController

logger = logging.getLogger(__name__)


@singleton
class WebSearch:
    """联网搜索"""

    def __init__(self):
        self._data = SharedData()
        self._obs = OBSController()

    def check_text_search(self):
        if not self._data.SearchTextList.empty() and self._data.is_SearchText == 2:
            self._data.is_SearchText = 1
            json_item = self._data.SearchTextList.get()
            prompt = json_item["prompt"]
            uid = json_item["uid"]
            username = json_item["username"]
            traceid = json_item["traceid"]

            search_result = self._baidu_web_search(prompt)
            llm_prompt = f'帮我在答案"{search_result}"中提取"{prompt}"的信息'
            logger.info(f"[{traceid}]搜索后提问: {llm_prompt}")

            self._data.QuestionList.put(
                {
                    "traceid": traceid,
                    "query": prompt,
                    "prompt": llm_prompt,
                    "uid": uid,
                    "username": username,
                }
            )
            self._data.is_SearchText = 2

    def _baidu_web_search(self, query: str) -> str:
        try:
            from webnet.ToolNet.tools.network.web_search import EnhancedWebSearch

            searcher = EnhancedWebSearch()
            results = searcher.search(query, engines=["baidu"], num_results=self._data.search_num)
            if isinstance(results, list) and results:
                return ";".join(
                    r.get("snippet", "").replace("\n", "").replace("\r", "") for r in results if r.get("snippet")
                )
        except Exception:
            logger.exception("【百度搜索】异常")
        return ""

    def msg_deal(self, traceid: str, query: str, uid: str, username: str) -> bool:
        text = ["查询", "查一下", "搜索"]
        is_contain = StringUtil.has_string_reg_list(f"^{text}", query)
        if is_contain is not None:
            num = StringUtil.is_index_contain_string(text, query)
            q = query[num:].strip()
            if q:
                self._data.SearchTextList.put(
                    {
                        "traceid": traceid,
                        "prompt": q,
                        "uid": uid,
                        "username": username,
                    }
                )
            return True
        return False
