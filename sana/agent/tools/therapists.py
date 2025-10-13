from typing import Literal, Annotated
import logging

from strands.tools import tool
from nova_act import NovaAct, NovaActError
from bedrock_agentcore.tools.browser_client import browser_session

from pydantic import BaseModel, Field

from sana.core.config import settings

logger = logging.getLogger(__name__)

class Therapist(BaseModel):
    name: Annotated[str, Field(...)]

class TherapistList(BaseModel):
    therapists: Annotated[list[Therapist], Field(...)]

@tool
def search_therapists(
    zip_code: str,
    topics: list[str],
    insurance: str | None = None,
    needs_medication_management: bool = False,
    therapist_gender_preference: Literal['female', 'male', 'non-binary', 'transgender'] | None = None,
    therapist_ethnicity_preference: Literal['Asian', 'Black', 'Hispanic', 'White'] | None = None,
    meeting_type_preference: Literal['in person', 'remote'] | None = None,
    limit: int = 5
) -> TherapistList:
    """
    Search for therapists using Headway, based on provided criteria.
    Use this tool once you have a clear understanding of the user's context, needs and preferences.
    If you do not have enough information, ask the user for more details before using this tool, for example:
    - "Do you have any insurance provider you would like to use?"
    - "Do you have any preferences regarding the gender or ethnicity of the therapist?"
    - "Would you prefer in-person or remote sessions?"
    This tool will connect to the Headway webpage and perform a search for therapists based on the provided criteria.
    This webpage can only search for therapists in the US. If the user is not located in the US, use the zip code 10001 (New York, NY).
    
    Example response:
        [
            {
                "name": "Dr. John Doe"
            }
        ]
    Args:
        zip_code (str): The zip code to search for therapists in.
        topics(list[str]): List of topics the therapist should specialize in.
        insurance (str | None): Insurance provider to filter therapists by.
        needs_medication_management (bool): Whether the user needs medication management.
        therapist_gender_preference (string or None): Preferred gender of the therapist. Leave as None for no preference.
                                                     Possible values: ['female', 'male', 'non-binary', 'transgender']
        therapist_ethnicity_preference (string or None): Preferred ethnicity of the therapist. Leave as None for no preference.
                                                        Possible values: ['Asian', 'Black', 'Hispanic', 'White']
        meeting_type_preference (str): Preferred meeting type. Leave as None for no preference.
                                       Possible values: ['in person', 'remote']
        limit (int): Maximum number of therapists to return.
    Returns:
        A list of therapists, each containing:
        - name (str): The name of the therapist.
    """
    all_therapists: list[Therapist] = []
    with browser_session(settings.AWS_REGION) as browser:
        ws_url, ws_headers = browser.generate_ws_headers()
        with NovaAct(
            nova_act_api_key=settings.AWS_NOVA_ACT_API_KEY,
            starting_page=settings.HEADWAY_BASE_URL,
            cdp_endpoint_url=ws_url,
            cdp_headers=ws_headers
        ) as nova:
            try:
                nova.act(
                    'Close any cookie banners, '
                    f'search for therapists in the {zip_code} zip code '
                    f'{f"using insurance {insurance}" if insurance else "leaving the insurance field blank. "}'
                    'Select Someone else as for whom you are looking for therapy. '
                    f'{"Select both talk therapy and medication management. " if needs_medication_management else "Select talk therapy and press next to continue. "}'
                    f'For the therapist gender preferences, select {"no preference" if not therapist_gender_preference else therapist_gender_preference}. '
                    f'For the therapist ethnicity preferences, select {"no preference" if not therapist_ethnicity_preference else therapist_ethnicity_preference}. Press next to continue. '
                    f'For the meeting type preference, select {"either" if not meeting_type_preference else meeting_type_preference}. Press next to continue. '
                    f'For the topics, select the ones that apply from the following list: ({", ".join(topics)}). Press next to continue and wait for the results page to pop up. '
                )
                for _ in range(limit):
                    result = nova.act(
                        "Return the currently visible list of therapists. "
                        "If there are no therapists visible, or you reached the end of the page, return an empty list. "
                        "Do not include therapists whose information is not fully visible. "
                        "To fill in the next_available_appointment field, parse the date in the format YYYY-MM-DD."
                        'To extract the URL, click the View profile button and copy the page URL, then press Alt + Left Arrow to go back to the results page. ',
                        schema=TherapistList.model_json_schema()
                    )
                    if not result.matches_schema:
                        logger.error(f'Invalid schema returned from Nova Act: {result}')
                        break
                    therapist_list = TherapistList.model_validate(result.parsed_response)
                    all_therapists.extend(therapist_list.therapists)
                    if len(all_therapists) >= limit:
                        break
                    nova.act("Scroll down the page")
                    return TherapistList(therapists=all_therapists)
            except NovaActError as e:
                logger.error(f'Nova Act interaction failed: {e}')
                pass
            except Exception as e:
                logger.error(f'Unexpected error during Nova Act interaction: {e}')
                raise e