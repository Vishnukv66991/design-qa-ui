import { render, screen } from '@testing-library/react';
import App from './App';

// FIX: Test for text that actually exists in the app (not the default CRA placeholder)
test('renders the Design QA Tool heading', () => {
  render(<App />);
  const heading = screen.getByText(/Design QA Tool/i);
  expect(heading).toBeInTheDocument();
});

test('renders the Run Analysis button', () => {
  render(<App />);
  const button = screen.getByRole('button', { name: /Run Analysis/i });
  expect(button).toBeInTheDocument();
});
