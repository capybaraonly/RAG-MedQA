
#
import json


def get_json_result_from_llm_response(response_str: str) -> dict:
    """
    Parse the LLM response string to extract JSON content.
    The function looks for the first and last curly braces to identify the JSON part.
    If parsing fails, it returns an empty dictionary.

    :param response_str: The response string from the LLM.
    :return: A dictionary parsed from the JSON content in the response.
    """
    try:
        clean_str = response_str.strip()
        if clean_str.startswith('```json'):
            clean_str = clean_str[7:]  # Remove the starting ```json
        if clean_str.endswith('```'):
            clean_str = clean_str[:-3]  # Remove the ending ```

        return json.loads(clean_str.strip())
    except (ValueError, json.JSONDecodeError):
        return {}
