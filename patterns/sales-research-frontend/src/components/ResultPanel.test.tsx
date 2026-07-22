// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CitationsList } from "./ResultPanel";

describe("CitationsList", () => {
  it("does not create a link for javascript URLs", () => {
    render(
      <CitationsList
        items={[
          {
            title: "Unsafe citation",
            url: "javascript:alert(1)",
            quote: "Untrusted",
          },
        ]}
      />,
    );

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("Unsafe citation")).toBeInTheDocument();
  });
});
