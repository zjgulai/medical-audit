import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";

describe("HomePage", () => {
  it("uses the login surface as the production root entry", () => {
    render(<HomePage />);

    expect(screen.getByRole("heading", { name: "登录工作台" })).toBeInTheDocument();
    expect(screen.queryByText("今日工作台")).not.toBeInTheDocument();
  });
});
