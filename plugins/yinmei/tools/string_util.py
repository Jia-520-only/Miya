import re


class StringUtil:
    @staticmethod
    def fuzzy_match_list(pattern, string_list):
        matches = []
        p = re.compile(pattern)
        for s in string_list:
            if p.search(s):
                matches.append(s)
        return matches

    @staticmethod
    def is_index_contain_string(string_array, target_string):
        for s in string_array:
            if s in target_string:
                return target_string.find(s) + len(s)
        return 0

    @staticmethod
    def is_index_nocontain_string(string_array, target_string):
        i = 0
        for s in string_array:
            i += 1
            if s in target_string:
                return i
        return 0

    @staticmethod
    def rfind_index_contain_string(string_array, target_string):
        for s in string_array:
            num = target_string.rfind(s)
            if num > 0:
                return num + len(s)
        return 0

    @staticmethod
    def has_string_reg_list(regxlist, s):
        regx = regxlist.replace("[", "(").replace("]", ")").replace(",", "|").replace("'", "").replace(" ", "")
        return re.search(regx, s)

    @staticmethod
    def isNone(text):
        if text is None:
            return ""
        return text

    @staticmethod
    def has_field(json_data, field):
        return field in json_data

    @staticmethod
    def filter(text, filter_prompt_str):
        fstr = filter_prompt_str.replace("\\n", "").lower()
        parts = fstr.split(",")
        for s in parts:
            text = text.lower().replace(s.lower(), "")
        return text

    @staticmethod
    def filter_html_tags(text):
        pattern = r"\[.*?\]|<.*?>|\(.*?\)|\n"
        return re.sub(pattern, "", text)
