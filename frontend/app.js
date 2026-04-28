const form = document.getElementById("ttsForm");
const result = document.getElementById("result");
const submitBtn = document.getElementById("submitBtn");
const textInput = document.getElementById("text");
const genderInput = document.getElementById("gender");
const exampleButtons = document.querySelectorAll(".example-btn");
const talkForm = document.getElementById("talkForm");
const talkSubmitBtn = document.getElementById("talkSubmitBtn");
const providerInput = document.getElementById("provider");
const modelInput = document.getElementById("model");
const talkPromptInput = document.getElementById("talkPrompt");
const playerWrap = document.getElementById("playerWrap");
const audioPlayer = document.getElementById("audioPlayer");

const setAndPlayAudio = async (rawAudioUrl) => {
    const normalizedAudioUrl = rawAudioUrl.startsWith("/") ? rawAudioUrl : `/${rawAudioUrl}`;
    audioPlayer.src = normalizedAudioUrl;
    audioPlayer.load();
    playerWrap.classList.remove("hidden");

    try {
        await audioPlayer.play();
    } catch (playError) {
        result.textContent = `${result.textContent}\n\nAutoplay blocked by browser. Press play on audio player.`;
    }
};
//example buttons to fill text input
exampleButtons.forEach((button) => {
    button.addEventListener("click", () => {
        textInput.value = button.dataset.text || "";
        textInput.focus();
    });
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const text = textInput.value.trim();
    const gender = genderInput.value;
    const saveDir = document.getElementById("saveDir").value.trim() || "output";

    if (!text) {
        result.textContent = "Please enter Bangla text.";
        return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Generating...";
    result.textContent = "Requesting audio generation...";
    playerWrap.classList.add("hidden");

    try {
        const response = await fetch("/tts", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                text,
                save_dir: saveDir,
                gender
            })
        });

        let data;
        try {
            data = await response.json();
        } catch (e) {
            const text = await response.text();
            result.textContent = `Error: ${response.status} - ${text}`;
            return;
        }

        if (!response.ok) {
            const msg = data.detail || data.error?.message || JSON.stringify(data);
            result.textContent = `Error: ${response.status} - ${msg}`;
            return;
        }

        result.textContent = JSON.stringify(data, null, 2);

        const rawAudioUrl = typeof data.audio_url === "string" ? data.audio_url : "";
        if (rawAudioUrl) {
            await setAndPlayAudio(rawAudioUrl);
        }
    } catch (error) {
        result.textContent = `Request failed: ${error.message}`;
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Generate Audio";
    }
});

talkForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const provider = providerInput.value;
    const model = modelInput.value.trim();
    const prompt = talkPromptInput.value.trim();
    const gender = genderInput.value;
    const saveDir = document.getElementById("saveDir").value.trim() || "output";

    if (!prompt) {
        result.textContent = "Please enter a prompt for AI talking pipeline.";
        return;
    }

    talkSubmitBtn.disabled = true;
    talkSubmitBtn.textContent = "Thinking + Speaking...";
    result.textContent = `Calling ${provider} and generating TTS audio...`;
    playerWrap.classList.add("hidden");

    try {
        const response = await fetch("/talk", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                provider,
                model: model || null,
                prompt,
                save_dir: saveDir,
                gender
            })
        });

        let data;
        try {
            data = await response.json();
        } catch (e) {
            const text = await response.text();
            result.textContent = `Error: ${response.status} - ${text}`;
            return;
        }

        if (!response.ok) {
            const msg = data.detail || data.error?.message || JSON.stringify(data);
            result.textContent = `Error: ${response.status} - ${msg}`;
            return;
        }

        result.textContent = JSON.stringify(data, null, 2);
        const rawAudioUrl = typeof data.audio_url === "string" ? data.audio_url : "";
        if (rawAudioUrl) {
            await setAndPlayAudio(rawAudioUrl);
        }
    } catch (error) {
        result.textContent = `Request failed: ${error.message}`;
    } finally {
        talkSubmitBtn.disabled = false;
        talkSubmitBtn.textContent = "Ask AI + Speak";
    }
});