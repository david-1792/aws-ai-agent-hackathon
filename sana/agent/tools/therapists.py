from typing import Literal, Any
import logging

from strands.tools import tool
from nova_act import NovaAct, NovaActError
from bedrock_agentcore.tools.browser_client import browser_session

from pydantic import BaseModel, computed_field

from sana.core.config import settings

logger = logging.getLogger(__name__)

class Therapist(BaseModel):
    name: str
    in_person_sessions: bool | None
    remote_sessions: bool | None
    focus_areas: Any
    personality_traits: Any
    offers_free_consultation: bool | None
    next_available_appointment: str | None
    
class TherapistList(BaseModel):
    therapists: list[Therapist]

class FullTherapistInfo(Therapist):
    path: str

    @computed_field
    @property
    def url(self) -> str:
        return f'{settings.HEADWAY_BASE_URL}{self.path}'

@tool
def search_therapists(
    zip_code: str,
    topics: list[str],
    insurance: str | None = None,
    needs_medication_management: bool = False,
    therapist_gender_preference: Literal['female', 'male', 'non-binary', 'transgender'] | None = None,
    therapist_ethnicity_preference: Literal['asian', 'black', 'hispanic', 'white'] | None = None,
    meeting_type_preference: Literal['in person', 'remote'] | None = None,
    limit: int = 5
) -> list[FullTherapistInfo]:
    """
    Search for therapists using Headway, based on provided criteria.
    Use this tool once you have a clear understanding of the user's context, needs and preferences.
    If you do not have enough information, ask the user for more details before using this tool, for example:
    - "Do you have any insurance provider you would like to use?"
    - "Are you taking any medication for your mental health currently?"
    - "Do you have any preferences regarding the gender of your therapist?"
    - "Do you have any preferences regarding the ethnicity of your therapist? Maybe someone who understands your cultural background?"
    - "Would you prefer in-person or remote sessions?"
    This tool will connect to the Headway webpage and perform a search for therapists based on the provided criteria.
    This webpage can only search for therapists in the US. If the user is not located in the US, use the zip code 10001 (New York, NY).
    The tool can take a very long time to complete so make sure to tell the user that you are searching for therapists and it may take a few minutes.
    Ask all of the questions you need to ask the user before calling this tool, as you will not be able to ask any follow-up questions.
    
    Example response:
        [
            {
                "name": "Dr. John Doe",
                "in_person_sessions": true,
                "remote_sessions": true,
                "focus_areas": ["anxiety", "depression"],
                "personality_traits": ["empathetic", "patient"],
                "offers_free_consultation": true,
                "next_available_appointment": "2023-10-15",
                "url": "https://www.headway.co/therapists/john-doe
            }
        ]
    Args:
        zip_code (str): The zip code to search for therapists in.
        topics(list[str]): List of topics the therapist should specialize in.
                           Possible values: ['adhd', 'anxiety, 'ocd', 'stress', 'depression', 'relationship issues', 'bipolar disorder', 'eating disorders', 'grief', 'substance abuse', 'trauma and ptsd', 'anger management', 'sleep disorders', 'maternal health', 'infertility', 'family issues', 'relationship issues', 'lgbtq+']
                           This list must contain less than 3 topics long. Choose ONLY the most relevant topics for the user. Do not include topics that are not available or that are not directly related to the user.
        insurance (str | None): Insurance provider to filter therapists by.
        needs_medication_management (bool): Whether the user needs medication management.
        therapist_gender_preference (string | None): Preferred gender of the therapist. Leave as None for no preference.
                                                     Possible values: ['female', 'male', 'non-binary', 'transgender']
        therapist_ethnicity_preference (string | None): Preferred ethnicity of the therapist. Leave as None for no preference.
                                                        Possible values: ['asian', 'black', 'hispanic', 'white']
        meeting_type_preference (str | None): Preferred meeting type. Leave as None for no preference.
                                       Possible values: ['in person', 'remote']
        limit (int): Maximum number of therapists to return. Default is 5.
    Returns:
        A list of therapists, each containing:
        - name (str): The name of the therapist.
        - distance_in_miles (float | None): Distance from the provided zip code, if available.
        - in_person_sessions (bool): Whether the therapist offers in-person sessions.
        - remote_sessions (bool): Whether the therapist offers remote sessions.
        - focus_areas (list[str]): List of focus areas the therapist specializes in.
        - personality_traits (list[str]): List of personality traits of the therapist.
        - offers_free_consultation (bool): Whether the therapist offers a free consultation.
        - next_available_appointment (str): Date of the next available appointment in MM-DD format.
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
                )
                nova.act(
                    'You will complete a multi-step form to filter therapists. Select next to continue to the next step. '
                    'Select Someone else as for whom you are looking for therapy. '
                    f'{"Select both talk therapy and medication management. " if needs_medication_management else "Select talk therapy. "}'
                    f'For the therapist gender preferences, select {"no preference" if not therapist_gender_preference else therapist_gender_preference}. '
                    f'For the therapist ethnicity preferences, select {"no preference" if not therapist_ethnicity_preference else therapist_ethnicity_preference}.'
                    f'For the meeting type preference, select {"either" if not meeting_type_preference else meeting_type_preference}. Do not press next. '
                    'Stop once you are in the Step 4: How can a therapist help? section. '
                )
                nova.act(
                    f'From the shown topics, select only the ones that are available from the following: ({", ".join(topics)}). '
                    'If a topic is not available, skip it. Do not scroll down to search for it. '
                    'Press next to continue and wait for the results page to pop up. '
                )

                for _ in range(limit):
                    result = nova.act(
                        "Return the currently visible list of therapists. "
                        "Omit therapists whose information is not fully visible. "
                        "A therapist's information is fully visible if you can see complete card. "
                        "Do not scroll down the page, just work with the currently visible therapists. "
                        "Make sure that the name is correctly spelled and capitalized. "
                        "To fill in the next_available_appointment field, parse the date in the format MM-DD."
                        "If an offers free consultation text is visible, set the offers_free_consultation field to true, otherwise false. ",
                        schema=TherapistList.model_json_schema()
                    )

                    if not result.matches_schema:
                        logger.error(f'Invalid schema returned from Nova Act: {result}')
                        continue

                    therapist_list = TherapistList.model_validate(result.parsed_response)
                    for therapist in therapist_list.therapists:
                        if not therapist.name or not therapist.next_available_appointment:
                            continue

                        all_therapists.append(therapist)
                        if len(all_therapists) >= limit:
                            break

                    nova.act("Scroll down the page")
                
                full_therapist_info_list: list[FullTherapistInfo] = []
                for therapist in all_therapists:
                    try:
                        path = nova.page.get_by_role('link', name=therapist.name).first.get_attribute('href')
                    except Exception:
                        try:
                            therapist_first_name, therapist_last_name = therapist.name.split(' ', 1)
                            path = nova.page.get_by_role('link', name=f'{therapist_first_name} {therapist_last_name[0]}').first.get_attribute('href')
                        except Exception as e:
                            logger.error(f'Failed to get profile link for therapist {therapist.name}: {e}')
                            continue

                    therapist_full_info = FullTherapistInfo(**therapist.model_dump(), path=path)
                    if therapist_full_info.name and therapist_full_info.next_available_appointment and therapist_full_info.url:
                        full_therapist_info_list.append(therapist_full_info)

                return full_therapist_info_list
            except NovaActError as e:
                logger.error(f'Nova Act interaction failed: {e}')
                pass
            except Exception as e:
                logger.error(f'Unexpected error during Nova Act interaction: {e}')
                raise e