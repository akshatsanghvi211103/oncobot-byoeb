# Introduction 
BYOeB (Build Your Own Expert Bot) is a platform designed to build expert-in-the-loop WhatsApp-based chatbots. It enables developers to build chatbots that leverages human expertise to verify and edit responses. It is particularly valuable in fields like medicine and law. The platform offers various features, such as support to integrate custom knowledge base, compatibility with multiple languages, supports both text and audio inputs/outputs, and the ability to improve the knowledge base using edits provided by experts.

**Follow the `Local installation` instructions below, and use the steps provided in `CUSTOMISE.md` to create your own expert-in-the-loop chatbot.**

# Local installation
## Creating virtual environment and installing dependencies
```console
> virtualenv .venv
> source .venv/bin/activate
> pip install -r requirements.txt
> sudo apt-get update
> sudo apt install g++ ffmpeg
```

## Azure dependencies setup for language and audio processing
```console
> wget -O - https://www.openssl.org/source/openssl-1.1.1u.tar.gz | tar zxf -
> cd openssl-1.1.1u
> ./config --prefix=/usr/local
> make -j $(nproc)
> sudo make install_sw install_ssldirs
> sudo ldconfig -v
> export SSL_CERT_DIR=/etc/ssl/certs   
> export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
> sudo apt-get install build-essential libssl-dev ca-certificates libasound2 wget
```

## For ngrok hosting
```console
> curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
  sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
  echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
  sudo tee /etc/apt/sources.list.d/ngrok.list && \
  sudo apt update && sudo apt install ngrok
```
Create a ngrok account online at https://ngrok.com/, and then add authication token using cmd line.
```console
> ngrok config add-authtoken <insert token here>
> ngrok http 5000
```

## Start the bot
Fill `keys.env` file with the required keys and credentials (of Azure Open AI, Azure AI Translator, Azure Storage, WhatsApp, etc.).

```console
> source keys.env
> flask run
```
If `flask run` is giving error, instead use `python3 app.py`.

# Explanation of Python scripts

### Structure
- `app.py`: It has the base code to run flask. All requests are directed from here.
- `start.sh`: Start up script for Azure related services. Installs required linux libraries and syncs knowledge base with past updates.
- `src/response`: It contains the Responder class that handles the response of an incoming message. The class should be derived from BaseResponder class.
- `src/messenger`: It contains the Messenger class that has the functionality to send different types of messages (message, poll, audio, etc). Similar to Responder, WhatsappMessenger class is derived from BaseMessenger.

### Key source
- `src/conversation_database.py`: All pymongo databases are loaded here and important functions are defined. This includes long term database to store user records, conversation database to store conversation records and logging database that stores various calls logged by the bot.
- `src/knowledge_base.py`: LLM based functions are defined here (answer query, generate correction, follow up questions, update response).
- `src/azure_language_tools.py`: Translation, TTS and Speech to Text.
- `src/onboard.py`: Onboarding webhook is directed here.
- `src/utils`: miscellenous utils.

### CronJob
- `cron_jobs/escalate.py`: Escalation of unasnwered queries to the respective senior experts take place here.
- `cron_jobs/send_email.py`: Email is sent with the sheet to the expert for KB updation. They can respond with Yes/No against every correction.
- `cron_jobs/kb_update.py`: Updation of Knowledge Base takes place here, the script pulls data from google sheet for the same.
- `cron_jobs/user_reminder.py`: A reminder message is sent to the users with this script.
- `cron_jobs/expert_reminder.py`: Used to send reminders to the expert (i.e doctors, staff) to continue interacting with the bot.
- `cron_jobs/account_expiration.py`: This script automatically expires accounts based on selected field (e.g surgery date for a patient).
- To execute cronjobs, we use a time trigger Azure function that sends an API request to the bot endpoint. For that, add the cron expressions in `cron.txt`. In the `scheduler` folder, the code for Azure function is also provided.

### Pre-processing
- `processing/create_llm_prompts.py`: Creates prompts using config.yaml for specific use cases.
- `processing/create_embeddings.py`: Creates ChromaDB from raw documents using OpenAI Embedding Function. 
- `processing/sync_kb.py`: Synchronizes the knowledge base with all the past KB updates.
- `processing/translate_introductions.py`: Translate onboarding/introduction messages.
- `processing/translate_suggestion_questions.py`: Translate onboarding questions.
- `processing/translate_language_prompt.py`: Translate the chose language question during onboarding.
- `processing/generate_audio_onboarding.py`: Onboarding Audio messages are saved.

# Assumptions
- Every response to the user query needs to be verified (and if needed, edited) by the expert.
- The output response depends on the GPT model used (specify appropriate key details in `keys.env`), and the `USER_PROMPT` specified in `config.yaml`.

# Contributing
This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

# Trademarks
This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft 
trademarks or logos is subject to and must follow 
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.


# Legal Notices
Microsoft and any contributors grant you a license to the Microsoft documentation and other content
in this repository under the [Creative Commons Attribution 4.0 International Public License](https://creativecommons.org/licenses/by/4.0/legalcode),
see the [LICENSE](LICENSE) file, and grant you a license to any code in the repository under the [MIT License](https://opensource.org/licenses/MIT), see the
[LICENSE-CODE](LICENSE-CODE) file.

Microsoft, Windows, Microsoft Azure, and/or other Microsoft products and services referenced in the documentation
may be either trademarks or registered trademarks of Microsoft in the United States and/or other countries.
The licenses for this project do not grant you rights to use any Microsoft names, logos, or trademarks.
Microsoft's general trademark guidelines can be found at http://go.microsoft.com/fwlink/?LinkID=254653.

Privacy information can be found at https://privacy.microsoft.com/en-us/

Microsoft and any contributors reserve all other rights, whether under their respective copyrights, patents,
or trademarks, whether by implication, estoppel, or otherwise.