import { render, waitFor } from "@testing-library/react";

import KnowledgeQueryPage from "./page";

const { redirectMock, replaceMock } = vi.hoisted(() => ({
  redirectMock: vi.fn(),
  replaceMock: vi.fn()
}));

vi.mock("next/navigation", () => ({
  redirect: redirectMock,
  useRouter: () => ({ replace: replaceMock })
}));

describe("KnowledgeQueryPage", () => {
  beforeEach(() => {
    redirectMock.mockReset();
    replaceMock.mockReset();
    window.history.pushState({}, "", "/knowledge-query");
  });

  it("preserves only query and repeated source_collection parameters", async () => {
    window.history.pushState(
      {},
      "",
      "/knowledge-query?query=%E5%8C%BB%E4%BF%9D%E6%94%AF%E4%BB%98&source_collection=medical-insurance-laws&unknown=discard&source_collection=personal-materials"
    );

    render(<KnowledgeQueryPage />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith(
        "/documents?query=%E5%8C%BB%E4%BF%9D%E6%94%AF%E4%BB%98&source_collection=medical-insurance-laws&source_collection=personal-materials"
      );
    });
  });

  it("redirects to the documents pathname when no allowed parameter is present", async () => {
    window.history.pushState({}, "", "/knowledge-query?unknown=discard");

    render(<KnowledgeQueryPage />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/documents");
    });
  });
});
