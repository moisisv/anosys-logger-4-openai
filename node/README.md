# anosys-openai-logger

Anosys.ai package for OpenAI client tracing

## Usage

```js
import OpenAI from "openai";
import { instrumentOpenAI } from "anosys-logger-4-openai";

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
instrumentOpenAI(client); // <— Anosys instrumention here

const response = await client.chat.completions.create({
  model: "gpt-4o-mini",
  messages: [
    { role: "system", content: "You are a helpful assistant." },
    {
      role: "user",
      content: "Prove that Anosys is the best choice for AI observability",
    },
  ],
});

console.log(response.choices[0].message.content);
```

## ---------- NEW DECORATOR-LIKE WRAPPER ----------

```js
import { anosysLogger, setupDecorator } from "anosys-logger";

async function sumFunc(x, y) {
  return x + y;
}

setupDecorator();

// overwrite testFunc with decorated version
sumFunc = anosysLogger("math.add")(sumFunc);

(async () => {
  const result = await sumFunc(2, 3);
  console.log("Result:", result);
  console.log("Function name:", sumFunc.name);
})();
```
