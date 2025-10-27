import React from 'react';
import { fireEvent, waitFor } from '@testing-library/react-native';
import { LearnerProfileSetupScreen } from '../LearnerProfileSetupScreen';
import { renderWithProviders } from '../../../test-utils/renderWithProviders';

const mutateAsyncMock = jest.fn();

jest.mock('../../../services/api/auth', () => ({
  useLearnerProfileSetup: () => ({
    mutateAsync: mutateAsyncMock,
    isLoading: false,
    isError: false,
  }),
}));

describe('LearnerProfileSetupScreen', () => {
  beforeEach(() => {
    mutateAsyncMock.mockResolvedValue({ level: 'Beginner', goals: ['Travel'], updatedAt: new Date().toISOString() });
  });

  it('requires level and at least one goal', async () => {
    const onSuccess = jest.fn();
    const { getByRole, getByText } = renderWithProviders(<LearnerProfileSetupScreen onSuccess={onSuccess} />);

    fireEvent.press(getByRole('button', { name: /continue/i }));

    await waitFor(() => {
      expect(getByText('Select your level')).toBeTruthy();
      expect(getByText('Choose at least one goal')).toBeTruthy();
    });
    expect(mutateAsyncMock).not.toHaveBeenCalled();
  });

  it('submits selected level and goals', async () => {
    const onSuccess = jest.fn();
    const { getByLabelText, getByRole, getAllByRole } = renderWithProviders(
      <LearnerProfileSetupScreen onSuccess={onSuccess} />
    );

    fireEvent.changeText(getByLabelText('level-input'), 'Intermediate');
    const goalOptions = getAllByRole('checkbox');
    fireEvent.press(goalOptions[0]);
    fireEvent.press(getByRole('button', { name: /continue/i }));

    await waitFor(() => {
      expect(mutateAsyncMock).toHaveBeenCalledWith({
        level: 'Intermediate',
        goals: [expect.any(String)],
      });
      expect(onSuccess).toHaveBeenCalled();
    });
  });
});
