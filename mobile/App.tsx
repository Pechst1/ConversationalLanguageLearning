import 'react-native-gesture-handler';
import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { enableScreens } from 'react-native-screens';
import { RootNavigator } from './src/navigation/RootNavigator';
import { colors } from './src/ui';
import { LearnerProvider } from './src/context/LearnerContext';
import type { AuthTokens } from './src/types/api';

enableScreens();

export default function App() {
  const [tokens, setTokens] = React.useState<AuthTokens | null>(null);

  const handleAuthenticated = React.useCallback((next: AuthTokens) => {
    setTokens(next);
  }, []);

  const handleSignOut = React.useCallback(() => {
    setTokens(null);
  }, []);

  return (
    <SafeAreaProvider>
      <LearnerProvider authTokens={tokens}>
        <StatusBar style="dark" backgroundColor={colors.background} />
        <RootNavigator
          isAuthenticated={Boolean(tokens)}
          onAuthenticated={handleAuthenticated}
          onSignOut={handleSignOut}
        />
      </LearnerProvider>
    </SafeAreaProvider>
  );
}
