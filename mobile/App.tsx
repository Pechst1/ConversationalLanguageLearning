import 'react-native-gesture-handler';
import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { enableScreens } from 'react-native-screens';
import { RootNavigator } from './src/navigation/RootNavigator';
import { colors } from './src/ui';

enableScreens();

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = React.useState(false);

  return (
    <SafeAreaProvider>
      <StatusBar style="dark" backgroundColor={colors.background} />
      <RootNavigator isAuthenticated={isAuthenticated} onSignIn={() => setIsAuthenticated(true)} />
    </SafeAreaProvider>
  );
}
