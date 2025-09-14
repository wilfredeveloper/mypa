// Defining a data model.
class Resume {
  name string
  email string
  experience string[]
  skills string[]
}

// Create a function to extract the resume from a string.
function ExtractResume(resume: string) -> Resume {
  // Specify a client as provider/model-name
  // you can use custom LLM params with a custom client name from clients.baml like "client CustomHaiku"
  client AgenticGeminiRateLimited // Set OPENAI_API_KEY to use this client.
  prompt #"
    Extract from this content:
    {{ resume }}

    {{ ctx.output_format }}
  "#
}



// Test the function with a sample resume. Open the VSCode playground to run this.
test vaibhav_resume {
  functions [ExtractResume]
  args {
    resume #"
      Vaibhav Gupta is the founder of BoundaryML, bringing strong expertise in computer vision from his previous roles as an engineer at Google and Microsoft. His email is valib@boundaryml.com. With a background deeply rooted in cutting-edge CV engineering, he has contributed to impactful projects at two of the world’s leading tech companies before moving on to establish his own venture. Vaibhav is highly skilled in systems programming and performance optimization, with proficiency in Rust and C++, which he leverages to build efficient and scalable solutions.
    "#
  }
}
