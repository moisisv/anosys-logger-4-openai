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

async function sum(x, y) {
  return x + y;
}

//for consts use rename instead
let modulo = (x, y) => {
  return x % y;
};

const multiply = (x, y) => {
  return x * y;
};

setupDecorator();

// overwrite sum with decorated version
sum = anosysLogger("math.sum")(sum);
modulo = anosysLogger("math.modulo")(modulo);

//NOTE tou cannot decorate const functions with same name.
// create a new decorated reference
const loggedMultiply = anosysLogger("math.multiply")(multiply);

(async () => {
  const result = await modulo(3, 2);
  console.log("Result:", result);

  const result2 = await sum(2, 3);
  console.log("Result:", result2);

  //for const funtion
  const result3 = await loggedMultiply(2, 3);
  console.log("Result:", result3);
  console.log("Original name:", multiply.name);
  console.log("Decorated name:", loggedMultiply.name);
})();
```
