import json
import os
from io import BytesIO
import requests
from PIL import Image

from nostr_dvm.interfaces.dvmtaskinterface import DVMTaskInterface
from nostr_dvm.utils.admin_utils import AdminConfig
from nostr_dvm.utils.definitions import EventDefinitions
from nostr_dvm.utils.dvmconfig import DVMConfig, build_default_config
from nostr_dvm.utils.nip89_utils import NIP89Config, check_and_set_d_tag
from nostr_dvm.utils.output_utils import upload_media_to_hoster
from nostr_dvm.utils.zap_utils import get_price_per_sat

"""
This File contains a Module to generate an Image on replicate and receive results back. 

Accepted Inputs: Prompt (text)
Outputs: An url to an Image
Params: 
"""


class ImageGenerationReplicateSDXL(DVMTaskInterface):
    KIND: int = EventDefinitions.KIND_NIP90_GENERATE_IMAGE
    TASK: str = "text-to-image"
    FIX_COST: float = 120
    dependencies = [("nostr-dvm", "nostr-dvm"),
                    ("replicate", "replicate==0.21.1")]

    def __init__(self, name, dvm_config: DVMConfig, nip89config: NIP89Config,
                 admin_config: AdminConfig = None, options=None):
        dvm_config.SCRIPT = os.path.abspath(__file__)
        super().__init__(name, dvm_config, nip89config, admin_config, options)

    def is_input_supported(self, tags):
        for tag in tags:
            if tag.as_vec()[0] == 'i':
                input_value = tag.as_vec()[1]
                input_type = tag.as_vec()[2]
                if input_type != "text":
                    return False

            elif tag.as_vec()[0] == 'output':
                output = tag.as_vec()[1]
                if (output == "" or
                        not (output == "image/png" or "image/jpg"
                             or output == "image/png;format=url" or output == "image/jpg;format=url")):
                    print("Output format not supported, skipping..")
                    return False

        return True

    def create_request_from_nostr_event(self, event, client=None, dvm_config=None):
        request_form = {"jobID": event.id().to_hex() + "_" + self.NAME.replace(" ", "")}
        prompt = ""
        width = "1024"
        height = "1024"

        for tag in event.tags():
            if tag.as_vec()[0] == 'i':
                input_type = tag.as_vec()[2]
                if input_type == "text":
                    prompt = tag.as_vec()[1]

            elif tag.as_vec()[0] == 'param':
                print("Param: " + tag.as_vec()[1] + ": " + tag.as_vec()[2])
                if tag.as_vec()[1] == "size":
                    if len(tag.as_vec()) > 3:
                        width = (tag.as_vec()[2])
                        height = (tag.as_vec()[3])
                    elif len(tag.as_vec()) == 3:
                        split = tag.as_vec()[2].split("x")
                        if len(split) > 1:
                            width = split[0]
                            height = split[1]
                elif tag.as_vec()[1] == "model":
                    model = tag.as_vec()[2]
                elif tag.as_vec()[1] == "quality":
                    quality = tag.as_vec()[2]

        options = {
            "prompt": prompt,
            "size": width + "x" + height,
            "number": 1
        }
        request_form['options'] = json.dumps(options)

        return request_form

    def process(self, request_form):
        try:
            options = DVMTaskInterface.set_options(request_form)

            import replicate
            width = int(options["size"].split("x")[0])
            height = int(options["size"].split("x")[1])
            output = replicate.run(
                "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
                input={"prompt": options["prompt"],
                       "width": width,
                       "height": height,
                       "disable_safety_checker": True}
            )
            print(output[0])
            response = requests.get(output[0])
            image = Image.open(BytesIO(response.content)).convert("RGB")
            image.save("./outputs/image.jpg")
            result = upload_media_to_hoster("./outputs/image.jpg")
            return result

        except Exception as e:
            print("Error in Module")
            raise Exception(e)


# We build an example here that we can call by either calling this file directly from the main directory,
# or by adding it to our playground. You can call the example and adjust it to your needs or redefine it in the
# playground or elsewhere
def build_example(name, identifier, admin_config):
    dvm_config = build_default_config(identifier)
    admin_config.LUD16 = dvm_config.LN_ADDRESS
    profit_in_sats = 10
    dvm_config.FIX_COST = int(((4.0 / (get_price_per_sat("USD") * 100)) + profit_in_sats))

    nip89info = {
        "name": name,
        "image": "https://image.nostr.build/c33ca6fc4cc038ca4adb46fdfdfda34951656f87ee364ef59095bae1495ce669.jpg",
        "about": "I use Replicate to run StableDiffusion XL",
        "encryptionSupported": True,
        "cashuAccepted": True,
        "nip90Params": {
            "size": {
                "required": False,
                "values": ["1024:1024", "1024x1792", "1792x1024"]
            }
        }
    }

    nip89config = NIP89Config()
    nip89config.DTAG = check_and_set_d_tag(identifier, name, dvm_config.PRIVATE_KEY, nip89info["image"])
    nip89config.CONTENT = json.dumps(nip89info)

    return ImageGenerationReplicateSDXL(name=name, dvm_config=dvm_config, nip89config=nip89config,
                                        admin_config=admin_config)


def process_venv():
    args = DVMTaskInterface.process_args()
    dvm_config = build_default_config(args.identifier)
    dvm = ImageGenerationReplicateSDXL(name="", dvm_config=dvm_config, nip89config=NIP89Config(), admin_config=None)
    result = dvm.process(json.loads(args.request))
    DVMTaskInterface.write_output(result, args.output)

#if __name__ == '__main__':
#    process_venv()
    #env_path = Path('.env')
    #if env_path.is_file():
    #    print(f'loading environment from {env_path.resolve()}')
    #    dotenv.load_dotenv(env_path, verbose=True, override=True)
    #else:
    #    raise FileNotFoundError(f'.env file not found at {env_path} ')

    #admin_config = AdminConfig()
    #admin_config.REBROADCAST_NIP89 = False
    #admin_config.UPDATE_PROFILE = False
    #dvm = build_example("Stable Diffusion XL", "replicate_sdxl", admin_config)
    #dvm.run()

    #keep_alive()
